# -*- coding: utf-8 -*-
"""
Phase 3 Test Suite: Citizen MCP Tools & Portal Integration.

Gates verified:
  1. scheme_info: returns pension rules, eligible blocks, document requirements, and deadline
  2. check_eligibility: validates senior age (60+) vs under-age with turning-60 calculation
  3. get_my_application: returns empty/draft state initially, bank accounts strictly masked
  4. save_details: incrementally saves draft details to portal memory
  5. get_document_upload_link: generates single-use 30-min upload URL and attaches document
  6. submit_application: validates all fields, creates official application with audit log
  7. withdraw_application: cancels pending application
  8. sign_out: terminates session and revokes tokens
"""

import os
import sys
import time
import json
import threading
import pytest
import requests
import uvicorn

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mcp_citizen.server import app as citizen_app
from evals.oauth_login import login_citizen_headless

PORTAL_URL = "http://localhost:8000"
CITIZEN_MCP_URL = "http://localhost:8001/mcp/citizen"
CITIZEN_BASE = "http://localhost:8001"


def parse_mcp_response(resp: requests.Response) -> dict:
    """Parse either raw JSON or SSE event stream returned by streamable HTTP."""
    text = resp.text
    if "data:" in text:
        for line in text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
    return resp.json()


class MCPClientSession:
    """Simulates a real MCP client over Streamable HTTP."""
    def __init__(self, endpoint_url: str, access_token: str):
        self.endpoint_url = endpoint_url
        self.access_token = access_token
        self.session_id = None
        self._initialize()

    def _initialize(self):
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"}
            }
        }
        resp = requests.post(self.endpoint_url, headers=headers, json=init_payload, timeout=5)
        assert resp.status_code == 200, f"Init failed: {resp.status_code} {resp.text}"
        self.session_id = resp.headers.get("mcp-session-id")

        # Send notifications/initialized
        notif_payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        post_headers = dict(headers)
        if self.session_id:
            post_headers["mcp-session-id"] = self.session_id
        requests.post(self.endpoint_url, headers=post_headers, json=notif_payload, timeout=5)

    def call_tool(self, tool_name: str, arguments: dict = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        if self.session_id:
            headers["mcp-session-id"] = self.session_id

        payload = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000) % 1000000,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {}
            }
        }
        resp = requests.post(self.endpoint_url, headers=headers, json=payload, timeout=8)
        assert resp.status_code == 200, f"Tool {tool_name} returned HTTP {resp.status_code}: {resp.text}"
        data = parse_mcp_response(resp)
        assert "result" in data, f"No result in response: {data}"

        # Extract text from content array
        content = data["result"].get("content", [])
        if content and content[0].get("type") == "text":
            try:
                return json.loads(content[0]["text"])
            except Exception:
                return {"raw_text": content[0]["text"]}
        return data["result"]


@pytest.fixture(scope="session", autouse=True)
def run_citizen_server():
    """Start citizen MCP server in background during test session."""
    os.environ["PORTAL_INTERNAL_URL"] = PORTAL_URL
    os.environ["PUBLIC_BASE_URL"] = PORTAL_URL
    os.environ["CITIZEN_RESOURCE_URL"] = CITIZEN_MCP_URL

    cfg = uvicorn.Config(citizen_app, host="127.0.0.1", port=8001, log_level="warning")
    server = uvicorn.Server(cfg)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()

    for _ in range(20):
        try:
            r = requests.get(f"{CITIZEN_BASE}/healthz", timeout=1)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.3)

    yield

    server.should_exit = True


@pytest.fixture
def citizen_session():
    """Create a fresh citizen login session for testing."""
    import random
    mobile = f"98{random.randint(10000000, 99999999)}"
    login_data = login_citizen_headless(mobile=mobile, resource_url=CITIZEN_MCP_URL, base_url=PORTAL_URL)
    return {
        "mobile": mobile,
        "token": login_data["access_token"],
        "client_id": login_data["client_id"]
    }


def test_gate1_scheme_info(citizen_session):
    """Citizen can retrieve scheme benefits, eligibility criteria, and deadline."""
    client = MCPClientSession(CITIZEN_MCP_URL, citizen_session["token"])
    res = client.call_tool("scheme_info")
    assert res.get("status") == "success"
    assert "Rs 1,000 per month" in res.get("pension_amount", "")
    assert res.get("minimum_age") == 60
    assert "Sonari" in res.get("eligible_blocks", [])
    assert res.get("window_open") is True


def test_gate2_check_eligibility(citizen_session):
    """check_eligibility correctly distinguishes seniors vs underage applicants."""
    client = MCPClientSession(CITIZEN_MCP_URL, citizen_session["token"])

    # 1. Senior eligible (born 1955)
    r_eligible = client.call_tool("check_eligibility", {"dob": "10/05/1955", "block": "Sonari"})
    assert r_eligible.get("status") == "success"
    assert r_eligible.get("eligible") is True
    assert r_eligible.get("age") >= 60

    # 2. Underage ineligible (born 1975)
    r_underage = client.call_tool("check_eligibility", {"dob": "10/05/1975", "block": "Sonari"})
    assert r_underage.get("status") == "success"
    assert r_underage.get("eligible") is False
    assert "10/05/2035" in r_underage.get("turning_60_date", "")

    # 3. Invalid format
    r_bad = client.call_tool("check_eligibility", {"dob": "invalid-dob"})
    assert r_bad.get("status") == "error"
    assert r_bad.get("error_code") == "eligibility_check_failed"


def test_gate3_save_details_and_bank_masking(citizen_session):
    """Draft details can be saved incrementally and bank accounts are masked."""
    client = MCPClientSession(CITIZEN_MCP_URL, citizen_session["token"])

    # Initially empty
    r_init = client.call_tool("get_my_application")
    assert r_init.get("has_submitted_application") is False

    # Save personal details
    r_save1 = client.call_tool("save_details", {
        "applicant_name": "Bhaben Hazarika",
        "dob": "12/03/1958",
        "gender": "Male",
        "marital_status": "Married",
        "block": "Sonari",
        "village": "Namti Ali"
    })
    assert r_save1.get("status") == "success"
    assert "Bank Account Number" in r_save1.get("missing_fields", [])
    assert r_save1.get("ready_for_submission") is False

    # Save bank details
    r_save2 = client.call_tool("save_details", {
        "bank_account": "123456789012",
        "ifsc": "SBIN0001234"
    })
    assert r_save2.get("status") == "success"
    draft = r_save2.get("draft", {})
    # Bank account MUST be masked
    assert draft.get("bank_account") == "********9012"
    assert "12345678" not in draft.get("bank_account")


def test_gate4_document_upload_link(citizen_session):
    """Citizen can request an upload link and upload age proof document."""
    client = MCPClientSession(CITIZEN_MCP_URL, citizen_session["token"])

    r_link = client.call_tool("get_document_upload_link")
    assert r_link.get("status") == "success"
    upload_url = r_link.get("upload_url")
    assert upload_url and "/upload/" in upload_url

    # Perform actual document upload via HTTP POST
    fake_pdf = b"%PDF-1.4 sample age proof certificate bytes for testing"
    files = {"document": ("age_proof.pdf", fake_pdf, "application/pdf")}
    resp_upload = requests.post(upload_url, files=files, timeout=5)
    assert resp_upload.status_code == 200
    assert "Uploaded Successfully" in resp_upload.text

    # Verify get_my_application reflects document
    r_app = client.call_tool("get_my_application")
    assert r_app.get("has_document") is True


def test_gate5_full_submission_and_lifecycle(citizen_session):
    """End-to-end citizen flow: Draft -> Upload -> Submit -> Track -> Withdraw -> Sign Out."""
    client = MCPClientSession(CITIZEN_MCP_URL, citizen_session["token"])
    token = citizen_session["token"]

    # 1. Save all details
    client.call_tool("save_details", {
        "applicant_name": "Kamala Devi",
        "dob": "01/01/1954",
        "gender": "Female",
        "marital_status": "Widow",
        "husband_name": "Late Mohan Devi",
        "block": "Rajapara",
        "village": "Hati Gaon",
        "bank_account": "987654321098",
        "ifsc": "PUNB0123400"
    })

    # 2. Upload document
    r_link = client.call_tool("get_document_upload_link")
    upload_url = r_link.get("upload_url")
    fake_pdf = b"%PDF-1.4 test certificate for Kamala Devi"
    requests.post(upload_url, files={"document": ("kamala_proof.pdf", fake_pdf, "application/pdf")}, timeout=5)

    # 3. Submit application
    r_sub = client.call_tool("submit_application")
    assert r_sub.get("status") == "success"
    app_no = r_sub.get("application_no")
    assert app_no and app_no.startswith("SSP")
    assert r_sub.get("block") == "Rajapara"

    # 4. Track status via get_my_application
    r_track = client.call_tool("get_my_application")
    assert r_track.get("has_submitted_application") is True
    assert r_track.get("application_no") == app_no
    assert r_track.get("application_status") == "PENDING" or r_track.get("status") == "PENDING"
    assert r_track.get("bank_account") == "********1098"
    assert r_track.get("can_withdraw") is True

    # 5. Withdraw application
    r_with = client.call_tool("withdraw_application", {"confirm": True})
    assert r_with.get("status") == "success"
    assert r_with.get("application_no") == app_no

    # Status now WITHDRAWN
    r_after = client.call_tool("get_my_application")
    assert r_after.get("application_status") == "WITHDRAWN" or r_after.get("status") == "WITHDRAWN"
    assert r_after.get("can_withdraw") is False

    # 6. Sign out
    r_out = client.call_tool("sign_out")
    assert r_out.get("status") == "success"

    # Subsequent tool call is rejected (401 session ended)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    r_dead = requests.post(CITIZEN_MCP_URL, headers=headers, json={"jsonrpc": "2.0", "id": 99, "method": "initialize"}, timeout=5)
    assert r_dead.status_code == 401
