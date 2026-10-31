# -*- coding: utf-8 -*-
"""
Sewa Setu - Internal Agent API (/internal/v1/*)
Private endpoints consumed by MCP servers over the Docker network.
Protected by X-Internal-Service-Key.
Never routed publicly by Caddy.
"""

import os
import re
import json
import secrets
import hashlib
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, abort

import app as portal

agent_api = Blueprint("agent_api", __name__, url_prefix="/internal/v1")

INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "dev-internal-key-2026")
UPLOAD_LINK_TTL_MINUTES = 30

REQUIRED_FIELDS = [
    ("applicant_name", "Full Name"),
    ("dob", "Date of Birth"),
    ("gender", "Gender"),
    ("marital_status", "Marital Status"),
    ("village", "Village"),
    ("block", "Block"),
    ("bank_account", "Bank Account Number"),
    ("ifsc", "Bank IFSC Code"),
]


def mask_account(acc):
    if not acc:
        return ""
    clean = re.sub(r"[\s-]", "", str(acc))
    if len(clean) <= 4:
        return clean
    return "*" * (len(clean) - 4) + clean[-4:]


@agent_api.before_request
def _verify_internal_key():
    key = request.headers.get("X-Internal-Service-Key", "")
    if not secrets.compare_digest(key, INTERNAL_API_KEY):
        return jsonify({"error": "unauthorized", "message": "Invalid or missing internal service key"}), 401


def _extract_citizen_mobile():
    sub = request.headers.get("X-Subject", "")
    if not sub.startswith("citizen:"):
        return None
    mobile = sub.split(":", 1)[1].strip()
    return mobile if len(mobile) == 10 and mobile.isdigit() else None


def _extract_officer_username():
    sub = request.headers.get("X-Subject", "")
    if not sub.startswith("officer:"):
        return None
    username = sub.split(":", 1)[1].strip()
    return username if username else None


# ---------------------------------------------------------------------------
# Migration runner
# ---------------------------------------------------------------------------

def apply_migrations():
    """Ensure agent tables are present."""
    migration_file = os.path.join(portal.BASE_DIR, "migrations", "003_agent.sql")
    if os.path.exists(migration_file):
        with open(migration_file, "r") as f:
            sql = f.read()
        conn = portal.get_db()
        cur = conn.cursor()
        try:
            cur.execute(sql)
            conn.commit()
        except Exception as e:
            conn.rollback()
            portal.app.logger.error("Migration error: %s" % e)
        finally:
            cur.close()
            conn.close()


# ---------------------------------------------------------------------------
# Session Check
# ---------------------------------------------------------------------------

@agent_api.get("/session_check")
def session_check():
    sub = request.args.get("sub", "")
    client_id = request.args.get("client_id", "")
    jti = request.args.get("jti", "")

    if not sub:
        return jsonify({"valid": False, "reason": "Missing subject"}), 400

    conn = portal.get_db()
    cur = conn.cursor()
    now = datetime.now()

    # If program token (checked by jti)
    if jti:
        cur.execute("SELECT revoked_at, expires_at FROM oauth_program_tokens WHERE jti = %s", (jti,))
        row = cur.fetchone()
        cur.close(); conn.close()
        if not row:
            return jsonify({"valid": False, "reason": "Unknown program token"})
        revoked_at, expires_at = row
        if revoked_at is not None:
            return jsonify({"valid": False, "reason": "Program token revoked"})
        if expires_at and expires_at <= now:
            return jsonify({"valid": False, "reason": "Program token expired"})
        return jsonify({"valid": True})

    # Standard OAuth token session check
    cur.execute(
        """SELECT expires_at FROM oauth_refresh_tokens 
           WHERE subject = %s AND client_id = %s AND revoked_at IS NULL AND expires_at > %s 
           ORDER BY created_at DESC LIMIT 1""",
        (sub, client_id, now)
    )
    row = cur.fetchone()
    cur.close(); conn.close()

    if not row:
        return jsonify({"valid": False, "reason": "Sign-in session ended or revoked"})
    return jsonify({"valid": True, "expires_at": row[0].isoformat(timespec="seconds")})


# ---------------------------------------------------------------------------
# Citizen Endpoints
# ---------------------------------------------------------------------------

@agent_api.get("/scheme_info")
@agent_api.get("/citizen/scheme_info")
def citizen_scheme_info():
    hours = portal.deadline_remaining()
    return jsonify({
        "scheme_name": "Old Age Pension Scheme (Indira Gandhi / State Pension)",
        "department": "Department of Social Welfare, Government of Purvanchal",
        "monthly_pension": "₹250 per month",
        "minimum_age": portal.MIN_AGE,
        "sla_days": portal.SLA_DAYS,
        "blocks": portal.AGENT_ENABLED_BLOCKS,
        "deadline": portal.SCHEME_DEADLINE.strftime("%Y-%m-%d %H:%M"),
        "hours_left": hours,
        "is_window_open": hours is not None,
        "accepted_documents": [
            "Aadhaar Card",
            "Voter ID Card (EPIC)",
            "Birth Certificate",
            "Ration Card with DOB",
            "PAN Card"
        ],
        "help_note": "Applications can be drafted and submitted by seniors or family members. An age proof document is required before submission."
    })


@agent_api.post("/citizen/eligibility")
def citizen_eligibility():
    body = request.get_json(silent=True) or {}
    dob_raw = body.get("dob", "")
    dob = portal.parse_dob(dob_raw)
    if dob is None:
        return jsonify({
            "eligible": False,
            "error": "Date of birth must be given in DD/MM/YYYY format, e.g. 15/08/1954."
        }), 400

    today = portal.now_ist().date()
    if dob > today:
        return jsonify({
            "eligible": False,
            "error": "Date of birth cannot be in the future."
        }), 400

    age = portal.age_on(dob, today)
    if age > 110:
        return jsonify({
            "eligible": False,
            "error": "Applicant age cannot exceed 110 years."
        }), 400

    if age < portal.MIN_AGE:
        # Calculate turning 60 date
        turning_60 = dob.replace(year=dob.year + portal.MIN_AGE)
        return jsonify({
            "eligible": False,
            "age": age,
            "minimum_age": portal.MIN_AGE,
            "turning_60_date": turning_60.strftime("%d/%m/%Y"),
            "message": f"Applicant is currently {age} years old. The scheme requires age 60 or above. Applicant will become eligible on {turning_60.strftime('%d/%m/%Y')}."
        })

    return jsonify({
        "eligible": True,
        "age": age,
        "minimum_age": portal.MIN_AGE,
        "message": f"Applicant is {age} years old and satisfies the age criterion (60+ years)."
    })


@agent_api.get("/citizen/draft")
def citizen_draft_get():
    mobile = _extract_citizen_mobile()
    if not mobile:
        return jsonify({"error": "invalid_subject", "message": "Valid citizen subject required"}), 403

    conn = portal.get_db()
    cur = conn.cursor()
    cur.execute("SELECT data, doc_path, updated_at FROM agent_drafts WHERE mobile = %s", (mobile,))
    row = cur.fetchone()
    cur.close(); conn.close()

    draft_data = row[0] if row else {}
    doc_path = row[1] if row else ""

    missing = []
    for key, label in REQUIRED_FIELDS:
        val = draft_data.get(key)
        if not val or not str(val).strip():
            missing.append(label)
    if not doc_path:
        missing.append("Age Proof Document")

    errors, _ = portal.validate_application(draft_data, doc_path)

    display_data = dict(draft_data)
    if display_data.get("bank_account"):
        display_data["bank_account"] = mask_account(display_data["bank_account"])

    return jsonify({
        "draft": display_data,
        "has_document": bool(doc_path and os.path.exists(doc_path)),
        "doc_name": os.path.basename(doc_path) if doc_path else None,
        "missing": missing,
        "validation_errors": errors,
        "is_ready_for_submission": len(missing) == 0 and len(errors) == 0
    })


@agent_api.post("/citizen/draft")
def citizen_draft_save():
    mobile = _extract_citizen_mobile()
    if not mobile:
        return jsonify({"error": "invalid_subject", "message": "Valid citizen subject required"}), 403

    body = request.get_json(silent=True) or {}
    conn = portal.get_db()
    cur = conn.cursor()
    cur.execute("SELECT data, doc_path FROM agent_drafts WHERE mobile = %s", (mobile,))
    row = cur.fetchone()
    current_data = row[0] if row else {}
    current_doc = row[1] if row else ""

    # Merge allowed fields
    allowed_keys = [
        "applicant_name", "dob", "gender", "marital_status", "husband_name",
        "village", "block", "bank_account", "ifsc"
    ]
    for k in allowed_keys:
        if k in body and body[k] is not None:
            val = str(body[k]).strip()
            if k == "dob":
                # Normalize DOB format if given with hyphens
                val = val.replace("-", "/")
            elif k == "bank_account":
                val = re.sub(r"[\s-]", "", val)
            elif k == "ifsc":
                val = re.sub(r"[\s-]", "", val).upper()
            elif k == "gender":
                val = val.capitalize()
            elif k == "marital_status":
                val = val.capitalize()
                if val == "Widow":
                    val = "Widowed"
                elif val == "Single":
                    val = "Unmarried"
            current_data[k] = val

    cur.execute(
        """INSERT INTO agent_drafts (mobile, data, doc_path, updated_at) 
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (mobile) DO UPDATE SET 
             data = EXCLUDED.data,
             updated_at = EXCLUDED.updated_at""",
        (mobile, json.dumps(current_data), current_doc, datetime.now())
    )
    conn.commit()
    cur.close(); conn.close()

    missing = []
    for key, label in REQUIRED_FIELDS:
        val = current_data.get(key)
        if not val or not str(val).strip():
            missing.append(label)
    if not current_doc:
        missing.append("Age Proof Document")

    errors, _ = portal.validate_application(current_data, current_doc)

    display_data = dict(current_data)
    if display_data.get("bank_account"):
        display_data["bank_account"] = mask_account(display_data["bank_account"])

    return jsonify({
        "message": "Details saved to application draft.",
        "draft": display_data,
        "has_document": bool(current_doc and os.path.exists(current_doc)),
        "missing": missing,
        "validation_errors": errors,
        "is_ready_for_submission": len(missing) == 0 and len(errors) == 0
    })


@agent_api.post("/citizen/upload_link")
def citizen_upload_link():
    mobile = _extract_citizen_mobile()
    if not mobile:
        return jsonify({"error": "invalid_subject", "message": "Valid citizen subject required"}), 403

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("ascii")).hexdigest()
    expires_at = datetime.now() + timedelta(minutes=UPLOAD_LINK_TTL_MINUTES)

    conn = portal.get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO upload_links (token_hash, mobile, expires_at) VALUES (%s, %s, %s)",
        (token_hash, mobile, expires_at)
    )
    conn.commit()
    cur.close(); conn.close()

    upload_url = f"{portal.ISSUER}/upload/{raw_token}"
    return jsonify({
        "upload_url": upload_url,
        "expires_in_minutes": UPLOAD_LINK_TTL_MINUTES,
        "expires_at": expires_at.isoformat(timespec="seconds"),
        "instructions": "Open this link on your phone or computer to securely upload your age proof document (JPG, PNG, or PDF, maximum 5 MB)."
    })


@agent_api.post("/citizen/submit")
def citizen_submit():
    mobile = _extract_citizen_mobile()
    if not mobile:
        return jsonify({"error": "invalid_subject", "message": "Valid citizen subject required"}), 403

    body = request.get_json(silent=True) or {}
    client_name = body.get("client_name", "AI Assistant")

    conn = portal.get_db()
    cur = conn.cursor()

    try:
        # Postgres advisory lock on the mobile to prevent concurrent double-submission race
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (mobile,))

        # Idempotence: check if an active application already exists
        existing = portal.active_application(cur, mobile)
        if existing:
            conn.commit()
            return jsonify({
                "status": "already_submitted",
                "application_id": existing[0],
                "application_no": existing[1],
                "application_status": existing[2],
                "message": f"Application {existing[1]} is already active with status {existing[2]}."
            })

        # Fetch saved draft
        cur.execute("SELECT data, doc_path FROM agent_drafts WHERE mobile = %s", (mobile,))
        row = cur.fetchone()
        if not row:
            conn.rollback()
            return jsonify({
                "error": "no_draft",
                "message": "No draft application details found. Please save personal and bank details first."
            }), 400

        draft_data, doc_path = row[0], row[1]
        errors, cleaned = portal.validate_application(draft_data, doc_path)
        if errors:
            conn.rollback()
            return jsonify({
                "error": "validation_failed",
                "validation_errors": errors,
                "message": "Application cannot be submitted: " + "; ".join(errors)
            }), 400

        # Create application using the single canonical portal engine
        new_id, app_no = portal.create_application(cur, mobile, cleaned)

        # Audit row noting agent origin
        portal.write_audit(cur, new_id, "SUBMIT", f"applicant:{mobile}", f"via agent: {client_name}")

        # Clear the draft
        cur.execute("DELETE FROM agent_drafts WHERE mobile = %s", (mobile,))
        conn.commit()

        # Send confirmation SMS
        portal.send_sms(
            mobile,
            f"Sewa Setu: application {app_no} received via assistant. Track status at {portal.ISSUER}/status."
        )

        return jsonify({
            "status": "submitted",
            "application_id": new_id,
            "application_no": app_no,
            "application_status": "PENDING",
            "applicant_name": cleaned["applicant_name"],
            "block": cleaned["block"],
            "village": cleaned["village"],
            "message": f"Application {app_no} has been submitted successfully for {cleaned['applicant_name']}. Status is PENDING."
        }), 201

    except Exception as e:
        conn.rollback()
        portal.app.logger.error("Internal submit error: %s" % e)
        return jsonify({"error": "server_error", "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@agent_api.get("/citizen/status")
def citizen_status():
    mobile = _extract_citizen_mobile()
    if not mobile:
        return jsonify({"error": "invalid_subject", "message": "Valid citizen subject required"}), 403

    conn = portal.get_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, application_no, applicant_name, dob, village, block, 
                  bank_account, ifsc, status, submitted_at, decided_at, decided_by 
           FROM applications WHERE mobile = %s ORDER BY submitted_at DESC LIMIT 1""",
        (mobile,)
    )
    row = cur.fetchone()
    cur.close(); conn.close()

    if not row:
        return jsonify({
            "has_application": False,
            "message": "No pension application found for this mobile number."
        })

    app_id, app_no, name, dob, village, block, bank_acc, ifsc, status, sub_at, dec_at, dec_by = row
    return jsonify({
        "has_application": True,
        "application_id": app_id,
        "application_no": app_no,
        "applicant_name": name,
        "dob": dob.strftime("%d/%m/%Y") if dob else None,
        "village": village,
        "block": block,
        "bank_account": mask_account(bank_acc),
        "ifsc": ifsc,
        "status": status,
        "submitted_at": sub_at.strftime("%d/%m/%Y %H:%M") if sub_at else None,
        "decided_at": dec_at.strftime("%d/%m/%Y %H:%M") if dec_at else None,
        "decided_by": dec_by,
        "can_withdraw": status == "PENDING"
    })


@agent_api.post("/citizen/withdraw")
def citizen_withdraw():
    mobile = _extract_citizen_mobile()
    if not mobile:
        return jsonify({"error": "invalid_subject", "message": "Valid citizen subject required"}), 403

    body = request.get_json(silent=True) or {}
    if not body.get("confirm"):
        return jsonify({
            "error": "confirmation_required",
            "message": "Please confirm withdrawal by setting confirm=true."
        }), 400

    conn = portal.get_db()
    cur = conn.cursor()
    cur.execute(
        """UPDATE applications SET status = 'WITHDRAWN', decided_at = %s, decided_by = 'APPLICANT' 
           WHERE mobile = %s AND status = 'PENDING' RETURNING id, application_no""",
        (datetime.now(), mobile)
    )
    row = cur.fetchone()
    if row:
        portal.write_audit(cur, row[0], "WITHDRAW", f"applicant:{mobile}", "withdrawn via assistant")
        conn.commit()
        cur.close(); conn.close()
        return jsonify({
            "status": "withdrawn",
            "application_no": row[1],
            "message": f"Application {row[1]} has been withdrawn. You may now apply afresh if needed."
        })
    else:
        cur.close(); conn.close()
        return jsonify({
            "error": "not_pending",
            "message": "Only a pending application can be withdrawn."
        }), 400


@agent_api.post("/citizen/session_end")
def citizen_session_end():
    mobile = _extract_citizen_mobile()
    if not mobile:
        return jsonify({"error": "invalid_subject", "message": "Valid citizen subject required"}), 403

    subject = f"citizen:{mobile}"
    conn = portal.get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE oauth_refresh_tokens SET revoked_at = %s WHERE subject = %s AND revoked_at IS NULL",
        (datetime.now(), subject)
    )
    revoked_count = cur.rowcount
    conn.commit()
    cur.close(); conn.close()

    return jsonify({
        "status": "signed_out",
        "revoked_sessions": revoked_count,
        "message": "All active assistant sessions for this mobile have been terminated."
    })


# ---------------------------------------------------------------------------
# Officer Endpoints
# ---------------------------------------------------------------------------

@agent_api.get("/officer/queue")
def officer_queue():
    officer = _extract_officer_username()
    if not officer:
        return jsonify({"error": "invalid_subject", "message": "Valid officer subject required"}), 403

    block = request.args.get("block", "").strip()
    limit = min(50, max(1, int(request.args.get("limit", 20))))
    page = max(1, int(request.args.get("page", 1)))
    offset = (page - 1) * limit

    conn = portal.get_db()
    cur = conn.cursor()

    where_sql = "status = 'PENDING'"
    params = []
    if block:
        where_sql += " AND block = %s"
        params.append(block)

    # Count
    cur.execute(f"SELECT count(*) FROM applications WHERE {where_sql}", params)
    total_count = cur.fetchone()[0]

    # Query oldest first
    query_sql = f"""
        SELECT id, application_no, applicant_name, mobile, dob, village, block, 
               bank_account, ifsc, submitted_at 
        FROM applications WHERE {where_sql}
        ORDER BY submitted_at ASC LIMIT %s OFFSET %s
    """
    cur.execute(query_sql, params + [limit, offset])
    rows = cur.fetchall()
    cur.close(); conn.close()

    now = datetime.now()
    items = []
    for r in rows:
        app_id, app_no, name, mob, dob, vil, blk, bank, ifsc, sub_at = r
        age_in_days = (now - sub_at).days if sub_at else 0
        days_left_sla = max(0, portal.SLA_DAYS - age_in_days)
        is_overdue = age_in_days >= portal.SLA_DAYS

        items.append({
            "application_id": app_id,
            "application_no": app_no,
            "applicant_name": name,
            "mobile": mob,
            "dob": dob.strftime("%d/%m/%Y") if dob else "",
            "village": vil,
            "block": blk,
            "bank_account": mask_account(bank),
            "ifsc": ifsc,
            "submitted_at": sub_at.strftime("%Y-%m-%d %H:%M") if sub_at else "",
            "days_pending": age_in_days,
            "days_left_sla": days_left_sla,
            "is_overdue": is_overdue
        })

    return jsonify({
        "total_pending": total_count,
        "page": page,
        "limit": limit,
        "block_filter": block or None,
        "cases": items
    })


@agent_api.get("/officer/overdue_summary")
def officer_overdue_summary():
    officer = _extract_officer_username()
    if not officer:
        return jsonify({"error": "invalid_subject", "message": "Valid officer subject required"}), 403

    conn = portal.get_db()
    cur = conn.cursor()
    now = datetime.now()
    sla_cutoff = now - timedelta(days=portal.SLA_DAYS)

    # Total pending
    cur.execute("SELECT count(*) FROM applications WHERE status = 'PENDING'")
    total_pending = cur.fetchone()[0]

    # Total overdue
    cur.execute("SELECT count(*) FROM applications WHERE status = 'PENDING' AND submitted_at < %s", (sla_cutoff,))
    total_overdue = cur.fetchone()[0]

    # By block
    cur.execute(
        """SELECT block, 
                  count(*) as total_pending,
                  count(*) FILTER (WHERE submitted_at < %s) as overdue
           FROM applications WHERE status = 'PENDING'
           GROUP BY block ORDER BY total_pending DESC""",
        (sla_cutoff,)
    )
    blocks_summary = []
    for b, pend, ovr in cur.fetchall():
        blocks_summary.append({
            "block": b,
            "pending": pend,
            "overdue": ovr
        })

    # Nearest SLA breaches (urgent)
    cur.execute(
        """SELECT id, application_no, applicant_name, block, submitted_at 
           FROM applications WHERE status = 'PENDING' 
           ORDER BY submitted_at ASC LIMIT 5"""
    )
    urgent = []
    for r in cur.fetchall():
        days = (now - r[4]).days if r[4] else 0
        urgent.append({
            "application_id": r[0],
            "application_no": r[1],
            "applicant_name": r[2],
            "block": r[3],
            "days_pending": days,
            "days_left_sla": max(0, portal.SLA_DAYS - days)
        })

    cur.close(); conn.close()

    return jsonify({
        "total_pending": total_pending,
        "total_overdue": total_overdue,
        "sla_days": portal.SLA_DAYS,
        "blocks": blocks_summary,
        "urgent_cases": urgent,
        "statutory_note": "Applications pending over 15 days stand approved automatically under the Purvanchal Right to Public Services Act (deemed approval)."
    })


@agent_api.get("/officer/case/<int:app_id>")
def officer_view_case(app_id):
    officer = _extract_officer_username()
    if not officer:
        return jsonify({"error": "invalid_subject", "message": "Valid officer subject required"}), 403

    conn = portal.get_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, application_no, applicant_name, mobile, dob, gender, 
                  marital_status, husband_name, village, block, bank_account, 
                  ifsc, doc_path, status, submitted_at, decided_at, decided_by 
           FROM applications WHERE id = %s""",
        (app_id,)
    )
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return jsonify({"error": "not_found", "message": f"Application {app_id} not found."}), 404

    (app_id, app_no, name, mob, dob, gender, marital, husband, vil, blk,
     bank_acc, ifsc, doc_path, status, sub_at, dec_at, dec_by) = row

    # Fetch audit log
    cur.execute(
        "SELECT action, actor, note, at FROM audit_log WHERE application_id = %s ORDER BY at ASC",
        (app_id,)
    )
    audit_rows = [
        {"action": a[0], "actor": a[1], "note": a[2], "at": a[3].strftime("%Y-%m-%d %H:%M:%S") if a[3] else ""}
        for a in cur.fetchall()
    ]

    # Calculate review flags
    flags = []
    # 1. Underage at submission
    sub_date = sub_at.date() if sub_at else portal.now_ist().date()
    age_at_sub = portal.age_on(dob, sub_date) if dob else 0
    if age_at_sub < portal.MIN_AGE:
        flags.append({
            "flag": "UNDERAGE_AT_SUBMISSION",
            "severity": "HIGH",
            "message": f"Applicant was {age_at_sub} years old at submission time (minimum required: {portal.MIN_AGE})."
        })

    # 2. No document or missing file on disk
    if not doc_path:
        flags.append({
            "flag": "NO_DOCUMENT_PATH",
            "severity": "HIGH",
            "message": "No age proof document path recorded."
        })
    elif not os.path.exists(doc_path):
        flags.append({
            "flag": "DOCUMENT_FILE_MISSING",
            "severity": "MEDIUM",
            "message": f"Age proof file not found on disk at {doc_path}."
        })

    # 3. Malformed IFSC
    if not ifsc or not re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", ifsc):
        flags.append({
            "flag": "MALFORMED_IFSC",
            "severity": "MEDIUM",
            "message": f"IFSC '{ifsc}' does not conform to the standard 11-character format."
        })

    # 4. Shared bank account
    cur.execute(
        """SELECT count(*) FROM applications 
           WHERE bank_account = %s AND id != %s AND status IN ('PENDING', 'APPROVED', 'DEEMED_APPROVED')""",
        (bank_acc, app_id)
    )
    shared_count = cur.fetchone()[0]
    if shared_count > 0:
        flags.append({
            "flag": "SHARED_BANK_ACCOUNT",
            "severity": "INFO",
            "message": f"Bank account is shared with {shared_count} other active/approved application(s)."
        })

    cur.close(); conn.close()

    now = datetime.now()
    days_pending = (now - sub_at).days if sub_at else 0

    return jsonify({
        "application_id": app_id,
        "application_no": app_no,
        "applicant_name": name,
        "mobile": mob,
        "dob": dob.strftime("%d/%m/%Y") if dob else "",
        "age_at_submission": age_at_sub,
        "gender": gender,
        "marital_status": marital,
        "husband_name": husband,
        "village": vil,
        "block": blk,
        "bank_account": bank_acc,  # Full account shown in officer case dossier
        "ifsc": ifsc,
        "doc_path": doc_path,
        "has_document_file": bool(doc_path and os.path.exists(doc_path)),
        "status": status,
        "submitted_at": sub_at.strftime("%Y-%m-%d %H:%M:%S") if sub_at else "",
        "days_pending": days_pending,
        "days_left_sla": max(0, portal.SLA_DAYS - days_pending),
        "decided_at": dec_at.strftime("%Y-%m-%d %H:%M:%S") if dec_at else None,
        "decided_by": dec_by,
        "flags": flags,
        "audit_trail": audit_rows,
        "is_decidable": status == "PENDING"
    })


@agent_api.post("/officer/decide")
def officer_decide():
    officer = _extract_officer_username()
    if not officer:
        return jsonify({"error": "invalid_subject", "message": "Valid officer subject required"}), 403

    body = request.get_json(silent=True) or {}
    app_id = body.get("application_id")
    decision = (body.get("decision") or "").upper().strip()
    reason = (body.get("reason") or body.get("note") or "").strip()

    if not app_id:
        return jsonify({"error": "missing_id", "message": "application_id is required."}), 400
    if decision not in ("APPROVED", "REJECTED"):
        return jsonify({"error": "invalid_decision", "message": "Decision must be APPROVED or REJECTED."}), 400
    if decision == "REJECTED" and len(reason) < 5:
        return jsonify({
            "error": "reason_required",
            "message": "A specific reason is required when rejecting an application (minimum 5 characters)."
        }), 400

    conn = portal.get_db()
    cur = conn.cursor()

    # Query current state
    cur.execute("SELECT application_no, status, decided_by, decided_at FROM applications WHERE id = %s", (app_id,))
    row = cur.fetchone()
    if not row:
        cur.close(); conn.close()
        return jsonify({"error": "not_found", "message": f"Application {app_id} does not exist."}), 404

    app_no, current_status, decided_by, decided_at = row

    if current_status != "PENDING":
        cur.close(); conn.close()
        # Idempotence: No change, no audit row written
        return jsonify({
            "status": "already_decided",
            "current_status": current_status,
            "application_no": app_no,
            "decided_by": decided_by,
            "decided_at": decided_at.strftime("%Y-%m-%d %H:%M") if decided_at else "",
            "message": f"Application {app_no} was already {current_status} by {decided_by} on {decided_at.strftime('%d/%m/%Y') if decided_at else ''}."
        })

    # Update only if still PENDING
    now = datetime.now()
    cur.execute(
        """UPDATE applications 
           SET status = %s, decided_at = %s, decided_by = %s 
           WHERE id = %s AND status = 'PENDING' 
           RETURNING application_no, mobile""",
        (decision, now, officer, app_id)
    )
    updated = cur.fetchone()
    if not updated:
        cur.close(); conn.close()
        return jsonify({
            "status": "already_decided",
            "message": f"Application {app_no} was decided concurrently by another officer."
        })

    # Write audit log with officer username
    portal.write_audit(cur, app_id, decision, f"officer:{officer}", reason)
    conn.commit()

    # Send SMS notification
    mobile = updated[1]
    if decision == "APPROVED":
        portal.send_sms(mobile, f"Sewa Setu: your pension application {app_no} has been APPROVED.")
    else:
        portal.send_sms(mobile, f"Sewa Setu: your pension application {app_no} was not approved. Reason: {reason}.")

    cur.close(); conn.close()

    return jsonify({
        "status": "success",
        "decision": decision,
        "application_no": app_no,
        "decided_by": officer,
        "decided_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "reason": reason,
        "message": f"Application {app_no} has been {decision} by Block Officer {officer}."
    })
