# -*- coding: utf-8 -*-
"""
Sewa Setu - Block Officer MCP Server (Streamable HTTP, RFC 8707, RFC 9728)
Endpoint: /mcp/officer
Required scope: officer
System of Record: Sewa Setu Portal (/internal/v1/*)
"""

import os
import sys
import logging
from typing import Dict, Any, Optional

import requests
from starlette.responses import JSONResponse
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.server import AuthSettings

from common.auth import (
    SewaSetuTokenVerifier,
    get_protected_resource_metadata,
    get_subject_from_context,
)
from common.errors import format_tool_success, format_tool_error

logger = logging.getLogger("mcp.officer")

PORTAL_INTERNAL_URL = os.environ.get("PORTAL_INTERNAL_URL", "http://localhost:8000").rstrip("/")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
RESOURCE_URL = os.environ.get("OFFICER_RESOURCE_URL", "http://localhost:8002/mcp/officer").rstrip("/")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "dev-internal-key-2026")


def _call_internal(endpoint: str, method: str = "GET", subject: Optional[str] = None, data: Optional[Dict[str, Any]] = None) -> requests.Response:
    headers = {"X-Internal-Service-Key": INTERNAL_API_KEY}
    if subject:
        headers["X-Subject"] = subject
    url = f"{PORTAL_INTERNAL_URL}/internal/v1{endpoint}"
    if method == "GET":
        return requests.get(url, headers=headers, params=data, timeout=5)
    elif method == "POST":
        return requests.post(url, headers=headers, json=data, timeout=5)
    raise ValueError(f"Unsupported HTTP method {method}")


def create_officer_server() -> MCPServer:
    auth_cfg = AuthSettings(
        issuer_url=PUBLIC_BASE_URL,
        resource_server_url=RESOURCE_URL,
        required_scopes=["officer"],
        validate_token_resource=True,
    )
    verifier = SewaSetuTokenVerifier(resource_server_url=RESOURCE_URL)

    server = MCPServer(
        name="sewasetu-officer",
        title="Sewa Setu Pension Portal — Block Officer Assistant",
        description="Assists Block Development Officers in triaging, reviewing dossiers, and deciding pension applications.",
        instructions=(
            "You are the Sewa Setu block officer triage assistant. Provide concise, factual summaries (<120 words). "
            "Help officers prioritize cases facing the 15-day RTPS deemed approval deadline. "
            "Highlight verification flags such as duplicate bank accounts, underage applicants, or missing documents."
        ),
        version="1.0.0",
        auth=auth_cfg,
        token_verifier=verifier,
    )

    @server.tool(
        name="ping",
        description="Verify block officer assistant connectivity and authentication status",
    )
    async def ping() -> Dict[str, Any]:
        """Verify officer session connectivity."""
        try:
            role, officer_name = get_subject_from_context()
            return format_tool_success(
                message="Connected to block officer assistant",
                next_step="Request my_queue or overdue_summary to triage applications",
                data={"role": role, "officer": officer_name}
            )
        except Exception as e:
            return format_tool_error("unauthenticated", str(e), "Sign in via Departmental login to continue")

    @server.tool(
        name="my_queue",
        description="List pending pension applications in your assigned block, ordered oldest first",
    )
    async def my_queue(block: Optional[str] = None, page: int = 1, limit: int = 20) -> Dict[str, Any]:
        """Fetch pending application triage queue for officer review."""
        try:
            role, officer_name = get_subject_from_context()
            sub = f"officer:{officer_name}"

            # Default officer block assignment if not explicitly specified
            query_block = block
            if not query_block and officer_name.lower() == "anjali":
                query_block = "Sonari"

            params = {"page": page, "limit": limit}
            if query_block:
                params["block"] = query_block

            r = _call_internal("/officer/queue", subject=sub, data=params)
            res = r.json()
            if r.status_code == 200:
                cases = res.get("cases", [])
                total = res.get("total_pending", 0)
                next_step = "Use view_case with an application_no to inspect full dossier, or approve_case/reject_case." if cases else "Queue is clear."
                return format_tool_success(
                    message=f"Retrieved {len(cases)} pending case(s) for {query_block or 'all blocks'} (total pending: {total}).",
                    next_step=next_step,
                    data={
                        "total_pending": total,
                        "page": res.get("page", 1),
                        "block": query_block,
                        "cases": cases
                    }
                )
            return format_tool_error("queue_failed", res.get("message", "Failed to retrieve queue"), "Try again")
        except Exception as e:
            return format_tool_error("queue_error", str(e), "Check portal connection")

    @server.tool(
        name="overdue_summary",
        description="Get an executive summary of applications overdue or approaching the 15-day RTPS deemed-approval limit",
    )
    async def overdue_summary() -> Dict[str, Any]:
        """Review statutory SLA compliance and urgent cases."""
        try:
            role, officer_name = get_subject_from_context()
            sub = f"officer:{officer_name}"

            r = _call_internal("/officer/overdue_summary", subject=sub)
            res = r.json()
            if r.status_code == 200:
                total_pending = res.get("total_pending", 0)
                total_overdue = res.get("total_overdue", 0)
                urgent = res.get("urgent_cases", [])
                return format_tool_success(
                    message=f"SLA Summary: {total_pending} total pending, {total_overdue} currently overdue (>15 days).",
                    next_step="Inspect urgent cases immediately using view_case to take action before automatic deemed approval.",
                    data={
                        "total_pending": total_pending,
                        "total_overdue": total_overdue,
                        "sla_days": res.get("sla_days", 15),
                        "blocks": res.get("blocks", []),
                        "urgent_cases": urgent,
                        "statutory_note": res.get("statutory_note")
                    }
                )
            return format_tool_error("summary_failed", res.get("message", "Failed to load overdue summary"), "Try again")
        except Exception as e:
            return format_tool_error("summary_error", str(e), "Check portal connection")

    @server.tool(
        name="view_case",
        description="Inspect complete case dossier, verification flags, uploaded age proof document, and audit history",
    )
    async def view_case(application_no: str) -> Dict[str, Any]:
        """Load comprehensive application dossier for decision making."""
        try:
            role, officer_name = get_subject_from_context()
            sub = f"officer:{officer_name}"

            r = _call_internal(f"/officer/case/{application_no}", subject=sub)
            res = r.json()
            if r.status_code == 200:
                flags = res.get("flags", [])
                flag_summary = f"{len(flags)} review flag(s) identified." if flags else "No verification flags. Application appears regular."
                is_decidable = res.get("is_decidable", False)
                next_step = "Use approve_case or reject_case (reason required) to record your official decision." if is_decidable else f"Application is already {res.get('status')}."
                return format_tool_success(
                    message=f"Dossier loaded for {res.get('applicant_name')} ({res.get('application_no')}). {flag_summary}",
                    next_step=next_step,
                    data={
                        "application_no": res.get("application_no"),
                        "applicant_name": res.get("applicant_name"),
                        "mobile": res.get("mobile"),
                        "dob": res.get("dob"),
                        "age_at_submission": res.get("age_at_submission"),
                        "gender": res.get("gender"),
                        "marital_status": res.get("marital_status"),
                        "husband_name": res.get("husband_name"),
                        "village": res.get("village"),
                        "block": res.get("block"),
                        "bank_account": res.get("bank_account"),
                        "ifsc": res.get("ifsc"),
                        "status": res.get("status"),
                        "days_pending": res.get("days_pending"),
                        "days_left_sla": res.get("days_left_sla"),
                        "has_document_file": res.get("has_document_file"),
                        "flags": flags,
                        "audit_trail": res.get("audit_trail", []),
                        "is_decidable": is_decidable
                    }
                )
            elif r.status_code == 404:
                return format_tool_error("not_found", f"Application '{application_no}' does not exist", "Check application number and retry")
            return format_tool_error("view_failed", res.get("message", "Failed to view case"), "Try again")
        except Exception as e:
            return format_tool_error("view_case_error", str(e), "Check portal connection")

    @server.tool(
        name="approve_case",
        description="Approve a pending pension application with officer attribution and audit logging",
    )
    async def approve_case(application_no: str, remarks: Optional[str] = None) -> Dict[str, Any]:
        """Record official approval of an application."""
        try:
            role, officer_name = get_subject_from_context()
            sub = f"officer:{officer_name}"

            payload = {
                "application_no": application_no,
                "decision": "APPROVED",
                "reason": remarks or "Approved on departmental verification"
            }
            r = _call_internal("/officer/decide", method="POST", subject=sub, data=payload)
            res = r.json()
            if r.status_code == 200:
                app_no = res.get("application_no")
                return format_tool_success(
                    message=f"Application {app_no} has been APPROVED by {officer_name}.",
                    next_step="Approval has been logged in the audit trail and citizen notified via SMS.",
                    data={
                        "application_no": app_no,
                        "decision": "APPROVED",
                        "decided_by": officer_name,
                        "status": "APPROVED"
                    }
                )
            return format_tool_error("approval_failed", res.get("message", "Cannot approve application"), "Inspect case status using view_case")
        except Exception as e:
            return format_tool_error("approve_case_error", str(e), "Check portal connection")

    @server.tool(
        name="reject_case",
        description="Reject a pension application with mandatory justification recorded in the audit trail",
    )
    async def reject_case(application_no: str, reason: str) -> Dict[str, Any]:
        """Record official rejection with required justification."""
        try:
            if not reason or len(reason.strip()) < 5:
                return format_tool_error(
                    error_code="reason_required",
                    message="A specific, plain-language reason is mandatory when rejecting an application (minimum 5 characters).",
                    next_step="Provide a clear reason (e.g. 'Age proof document unreadable' or 'Under minimum age of 60 years')."
                )

            role, officer_name = get_subject_from_context()
            sub = f"officer:{officer_name}"

            payload = {
                "application_no": application_no,
                "decision": "REJECTED",
                "reason": reason.strip()
            }
            r = _call_internal("/officer/decide", method="POST", subject=sub, data=payload)
            res = r.json()
            if r.status_code == 200:
                app_no = res.get("application_no")
                return format_tool_success(
                    message=f"Application {app_no} has been REJECTED by {officer_name}.",
                    next_step="Rejection and stated reason recorded in the permanent audit trail; citizen notified via SMS.",
                    data={
                        "application_no": app_no,
                        "decision": "REJECTED",
                        "reason": reason.strip(),
                        "decided_by": officer_name,
                        "status": "REJECTED"
                    }
                )
            return format_tool_error("rejection_failed", res.get("message", "Cannot reject application"), "Check case status using view_case")
        except Exception as e:
            return format_tool_error("reject_case_error", str(e), "Check portal connection")

    return server


def create_officer_app():
    server = create_officer_server()

    @server.custom_route("/.well-known/oauth-protected-resource", methods=["GET", "OPTIONS"])
    async def protected_resource_metadata_root(request):
        meta = get_protected_resource_metadata(RESOURCE_URL, "officer")
        return JSONResponse(meta)

    @server.custom_route("/mcp/officer/.well-known/oauth-protected-resource", methods=["GET", "OPTIONS"])
    async def protected_resource_metadata_sub(request):
        meta = get_protected_resource_metadata(RESOURCE_URL, "officer")
        return JSONResponse(meta)

    @server.custom_route("/healthz", methods=["GET"])
    async def healthz(request):
        return JSONResponse({"status": "ok", "service": "mcp-officer"})

    return server.streamable_http_app(streamable_http_path="/mcp/officer")


app = create_officer_app()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8002"))
    uvicorn.run(app, host="0.0.0.0", port=port)
