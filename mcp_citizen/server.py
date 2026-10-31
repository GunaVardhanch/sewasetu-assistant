# -*- coding: utf-8 -*-
"""
Sewa Setu - Citizen MCP Server (Streamable HTTP, RFC 8707, RFC 9728)
Endpoint: /mcp/citizen
Required scope: citizen
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
from common.masking import mask_bank_account

logger = logging.getLogger("mcp.citizen")

PORTAL_INTERNAL_URL = os.environ.get("PORTAL_INTERNAL_URL", "http://localhost:8000").rstrip("/")
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
RESOURCE_URL = os.environ.get("CITIZEN_RESOURCE_URL", "http://localhost:8001/mcp/citizen").rstrip("/")
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


def create_citizen_server() -> MCPServer:
    auth_cfg = AuthSettings(
        issuer_url=PUBLIC_BASE_URL,
        resource_server_url=RESOURCE_URL,
        required_scopes=["citizen"],
        validate_token_resource=True,
    )
    verifier = SewaSetuTokenVerifier(resource_server_url=RESOURCE_URL)

    server = MCPServer(
        name="sewasetu-citizen",
        title="Sewa Setu Pension Assistant — Citizen Services",
        description="Assists citizens of Purvanchal with Indira Gandhi National Old Age Pension applications.",
        instructions=(
            "You are the Sewa Setu citizen assistant. Speak respectfully, warmly, and concisely (<120 words). "
            "Never disclose full bank account numbers; show only the last 4 digits. "
            "Help seniors check eligibility, draft details, upload age proof, and track their pension applications."
        ),
        version="1.0.0",
        auth=auth_cfg,
        token_verifier=verifier,
    )

    @server.tool(
        name="ping",
        description="Verify citizen assistant connectivity and authentication status",
    )
    async def ping() -> Dict[str, Any]:
        """Verify caller session connectivity."""
        try:
            role, mobile = get_subject_from_context()
            return format_tool_success(
                message="Connected to citizen assistant",
                next_step="Ask about scheme eligibility or check your application status",
                data={"role": role, "mobile": mobile[-4:].rjust(len(mobile), "*")}
            )
        except Exception as e:
            return format_tool_error("unauthenticated", str(e), "Sign in via OAuth to continue")

    @server.tool(
        name="scheme_info",
        description="Get overview, eligibility criteria, benefits, and deadline for the Old Age Pension Scheme",
    )
    async def scheme_info() -> Dict[str, Any]:
        """Retrieve authoritative scheme rules and current application window status."""
        try:
            r = _call_internal("/citizen/scheme_info")
            if r.status_code == 200:
                data = r.json()
                return format_tool_success(
                    message="Indira Gandhi National Old Age Pension Scheme provides financial assistance to senior citizens.",
                    next_step="Use check_eligibility with your date of birth, or save_details to start drafting an application.",
                    data={
                        "pension_amount": "Rs 1,000 per month",
                        "minimum_age": data.get("minimum_age", 60),
                        "eligible_blocks": data.get("blocks", []),
                        "accepted_documents": data.get("accepted_documents", []),
                        "deadline": data.get("deadline"),
                        "hours_left": data.get("hours_left"),
                        "window_open": data.get("is_window_open", True),
                    }
                )
            return format_tool_error("internal_error", "Failed to load scheme info", "Try again in a few moments")
        except Exception as e:
            return format_tool_error("network_error", str(e), "Check network connection to portal")

    @server.tool(
        name="check_eligibility",
        description="Check whether an applicant meets the age criteria for the Old Age Pension scheme",
    )
    async def check_eligibility(dob: str, block: Optional[str] = None) -> Dict[str, Any]:
        """Verify age eligibility using date of birth in DD/MM/YYYY format."""
        try:
            r = _call_internal("/citizen/eligibility", method="POST", data={"dob": dob, "block": block})
            res = r.json()
            if r.status_code == 200:
                if res.get("eligible"):
                    return format_tool_success(
                        message=res.get("message", "Applicant is eligible for the pension scheme."),
                        next_step="Use save_details to record your name, address, and bank information.",
                        data={"eligible": True, "age": res.get("age")}
                    )
                else:
                    return format_tool_success(
                        message=res.get("message", "Applicant is not yet eligible."),
                        next_step=f"Applicant will become eligible on {res.get('turning_60_date')} upon turning 60.",
                        data={
                            "eligible": False,
                            "age": res.get("age"),
                            "turning_60_date": res.get("turning_60_date")
                        }
                    )
            return format_tool_error("eligibility_check_failed", res.get("error", "Invalid date of birth"), "Provide date of birth in DD/MM/YYYY format, e.g. 15/08/1954")
        except Exception as e:
            return format_tool_error("network_error", str(e), "Retry eligibility check")

    @server.tool(
        name="get_my_application",
        description="Check current pension application status or view saved draft details for your signed-in mobile",
    )
    async def get_my_application() -> Dict[str, Any]:
        """Fetch active application status or in-progress draft for the authenticated citizen."""
        try:
            role, mobile = get_subject_from_context()
            sub = f"citizen:{mobile}"

            # 1. Check submitted application
            r_status = _call_internal("/citizen/status", subject=sub)
            if r_status.status_code == 200:
                app_data = r_status.json()
                if app_data.get("has_application"):
                    status = app_data.get("status")
                    return format_tool_success(
                        message=f"Application {app_data.get('application_no')} is currently {status}.",
                        next_step="You may withdraw if pending, or contact your Block Development Office for updates.",
                        data={
                            "has_submitted_application": True,
                            "application_no": app_data.get("application_no"),
                            "applicant_name": app_data.get("applicant_name"),
                            "status": status,
                            "block": app_data.get("block"),
                            "village": app_data.get("village"),
                            "bank_account": app_data.get("bank_account"),
                            "submitted_at": app_data.get("submitted_at"),
                            "can_withdraw": app_data.get("can_withdraw", False)
                        }
                    )

            # 2. If no submitted application, check draft
            r_draft = _call_internal("/citizen/draft", subject=sub)
            if r_draft.status_code == 200:
                draft_data = r_draft.json()
                draft = draft_data.get("draft", {})
                missing = draft_data.get("missing", [])
                ready = draft_data.get("is_ready_for_submission", False)
                return format_tool_success(
                    message="No submitted application found. A draft application is currently in progress." if draft else "No active or draft application found.",
                    next_step="Use submit_application to submit your completed draft." if ready else "Use save_details or get_document_upload_link to complete missing items.",
                    data={
                        "has_submitted_application": False,
                        "has_draft": bool(draft),
                        "draft": draft,
                        "missing_fields": missing,
                        "has_document": draft_data.get("has_document", False),
                        "ready_for_submission": ready,
                        "validation_errors": draft_data.get("validation_errors", [])
                    }
                )

            return format_tool_error("status_failed", "Unable to retrieve application records", "Try again shortly")
        except Exception as e:
            return format_tool_error("application_query_error", str(e), "Check portal connection")

    @server.tool(
        name="save_details",
        description="Save or update personal, residential, and bank details in your draft pension application",
    )
    async def save_details(
        applicant_name: Optional[str] = None,
        dob: Optional[str] = None,
        gender: Optional[str] = None,
        marital_status: Optional[str] = None,
        husband_name: Optional[str] = None,
        village: Optional[str] = None,
        block: Optional[str] = None,
        bank_account: Optional[str] = None,
        ifsc: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update draft pension application details in portal memory."""
        try:
            role, mobile = get_subject_from_context()
            sub = f"citizen:{mobile}"

            payload = {}
            if applicant_name is not None: payload["applicant_name"] = applicant_name
            if dob is not None: payload["dob"] = dob
            if gender is not None: payload["gender"] = gender
            if marital_status is not None: payload["marital_status"] = marital_status
            if husband_name is not None: payload["husband_name"] = husband_name
            if village is not None: payload["village"] = village
            if block is not None: payload["block"] = block
            if bank_account is not None: payload["bank_account"] = bank_account
            if ifsc is not None: payload["ifsc"] = ifsc

            r = _call_internal("/citizen/draft", method="POST", subject=sub, data=payload)
            res = r.json()
            if r.status_code == 200:
                missing = res.get("missing", [])
                ready = res.get("is_ready_for_submission", False)
                next_step = "Draft is complete! Use submit_application to submit." if ready else f"Remaining required items: {', '.join(missing)}."
                return format_tool_success(
                    message="Draft details saved successfully.",
                    next_step=next_step,
                    data={
                        "draft": res.get("draft"),
                        "missing_fields": missing,
                        "ready_for_submission": ready,
                        "validation_errors": res.get("validation_errors", [])
                    }
                )
            return format_tool_error("save_draft_failed", res.get("message", "Failed to save draft"), "Check submitted values")
        except Exception as e:
            return format_tool_error("save_details_error", str(e), "Please retry saving")

    @server.tool(
        name="get_document_upload_link",
        description="Generate a secure 30-minute web upload link to upload the citizen's age proof document",
    )
    async def get_document_upload_link() -> Dict[str, Any]:
        """Generate a one-time tokenized URL for file upload."""
        try:
            role, mobile = get_subject_from_context()
            sub = f"citizen:{mobile}"

            r = _call_internal("/citizen/upload_link", method="POST", subject=sub)
            res = r.json()
            if r.status_code == 200:
                upload_url = res.get("upload_url")
                return format_tool_success(
                    message="Secure document upload link generated (valid for 30 minutes).",
                    next_step="Open the upload link on your mobile or computer to upload your age proof (PDF, JPG, or PNG, max 5 MB).",
                    data={
                        "upload_url": upload_url,
                        "expires_in_minutes": res.get("expires_in_minutes", 30),
                        "expires_at": res.get("expires_at"),
                    }
                )
            return format_tool_error("upload_link_failed", res.get("message", "Could not generate link"), "Try again")
        except Exception as e:
            return format_tool_error("upload_link_error", str(e), "Check portal connection")

    @server.tool(
        name="submit_application",
        description="Submit the finalized draft pension application for block officer review",
    )
    async def submit_application() -> Dict[str, Any]:
        """Finalize and submit the active draft application."""
        try:
            role, mobile = get_subject_from_context()
            sub = f"citizen:{mobile}"

            r = _call_internal("/citizen/submit", method="POST", subject=sub, data={"client_name": "Citizen AI Assistant"})
            res = r.json()
            if r.status_code in (200, 201):
                app_no = res.get("application_no")
                return format_tool_success(
                    message=f"Application {app_no} submitted successfully! Status: PENDING.",
                    next_step="Your application is now in queue for Block Officer review. Track status anytime using get_my_application.",
                    data={
                        "application_no": app_no,
                        "applicant_name": res.get("applicant_name"),
                        "block": res.get("block"),
                        "application_status": res.get("application_status", "PENDING")
                    }
                )
            elif r.status_code == 400:
                errors = res.get("validation_errors", [])
                msg = res.get("message", "Validation failed before submission.")
                return format_tool_error(
                    error_code="submission_validation_failed",
                    message=msg,
                    next_step="Use save_details or get_document_upload_link to provide missing or corrected fields.",
                    details={"validation_errors": errors}
                )
            return format_tool_error("submit_failed", res.get("message", "Submission failed"), "Verify draft details")
        except Exception as e:
            return format_tool_error("submit_error", str(e), "Check portal connection")

    @server.tool(
        name="withdraw_application",
        description="Withdraw a pending pension application for the signed-in citizen",
    )
    async def withdraw_application(confirm: bool = True) -> Dict[str, Any]:
        """Cancel an existing pending application."""
        try:
            role, mobile = get_subject_from_context()
            sub = f"citizen:{mobile}"

            r = _call_internal("/citizen/withdraw", method="POST", subject=sub, data={"confirm": confirm})
            res = r.json()
            if r.status_code == 200:
                return format_tool_success(
                    message=res.get("message", "Application has been withdrawn successfully."),
                    next_step="You may submit a fresh application at any time if required.",
                    data={"application_status": "WITHDRAWN", "application_no": res.get("application_no")}
                )
            return format_tool_error("withdraw_failed", res.get("message", "Cannot withdraw application"), "Only pending applications can be withdrawn")
        except Exception as e:
            return format_tool_error("withdraw_error", str(e), "Check portal connection")

    @server.tool(
        name="sign_out",
        description="Sign out and revoke active assistant sessions for this mobile number",
    )
    async def sign_out() -> Dict[str, Any]:
        """End the citizen session and revoke authorization tokens."""
        try:
            role, mobile = get_subject_from_context()
            sub = f"citizen:{mobile}"

            r = _call_internal("/citizen/session_end", method="POST", subject=sub)
            res = r.json()
            if r.status_code == 200:
                return format_tool_success(
                    message="You have been signed out successfully. Assistant session ended.",
                    next_step="To use the assistant again, a new OTP sign-in will be required.",
                    data={"session_status": "signed_out"}
                )
            return format_tool_error("sign_out_failed", res.get("message", "Sign out failed"), "Close your browser window")
        except Exception as e:
            return format_tool_error("sign_out_error", str(e), "Close session")

    return server


def create_citizen_app():
    server = create_citizen_server()

    @server.custom_route("/.well-known/oauth-protected-resource", methods=["GET", "OPTIONS"])
    async def protected_resource_metadata_root(request):
        meta = get_protected_resource_metadata(RESOURCE_URL, "citizen")
        return JSONResponse(meta)

    @server.custom_route("/mcp/citizen/.well-known/oauth-protected-resource", methods=["GET", "OPTIONS"])
    async def protected_resource_metadata_sub(request):
        meta = get_protected_resource_metadata(RESOURCE_URL, "citizen")
        return JSONResponse(meta)

    @server.custom_route("/healthz", methods=["GET"])
    async def healthz(request):
        return JSONResponse({"status": "ok", "service": "mcp-citizen"})

    return server.streamable_http_app(streamable_http_path="/mcp/citizen")


app = create_citizen_app()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
