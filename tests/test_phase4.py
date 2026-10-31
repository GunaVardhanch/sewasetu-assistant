# -*- coding: utf-8 -*-
"""
Phase 4 Test Suite: Block Officer MCP Server & Decision Workflows.

Gates verified:
  1. my_queue: retrieves block-specific pending applications ordered oldest first
  2. overdue_summary: summarizes SLA compliance, overdue breaches, and block counts
  3. view_case: inspects full case dossier, flags (underage, shared account), and audit log
  4. approve_case: approves application, records named audit log (officer:anjali), idempotent
  5. reject_case: enforces mandatory reason, records rejection with justification in audit log
"""

import os
import sys
import time
import json
import random
import threading
import pytest
import requests
import uvicorn

# Ensure parent directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mcp_officer.server import app as officer_app
from evals.oauth_login import login_officer_headless, login_citizen_headless

PORTAL_URL = "http://localhost:8000"
OFFICER_MCP_URL = "http://localhost:8002/mcp/officer"
OFFICER_BASE = "http://localhost:8002"
INTERNAL_API_KEY = "dev-internal-key-2026"


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
                "clientInfo": {"name": "officer-test-client", "version": "1.0"}
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

        content = data["result"].get("content", [])
        if content and content[0].get("type") == "text":
            try:
                return json.loads(content[0]["text"])
            except Exception:
                return {"raw_text": content[0]["text"]}
        return data["result"]


@pytest.fixture(scope="session", autouse=True)
def run_officer_server():
    """Start officer MCP server in background during test session."""
    os.environ["PORTAL_INTERNAL_URL"] = PORTAL_URL
    os.environ["PUBLIC_BASE_URL"] = PORTAL_URL
    os.environ["OFFICER_RESOURCE_URL"] = OFFICER_MCP_URL

    cfg = uvicorn.Config(officer_app, host="127.0.0.1", port=8002, log_level="warning")
    server = uvicorn.Server(cfg)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()

    for _ in range(20):
        try:
            r = requests.get(f"{OFFICER_BASE}/healthz", timeout=1)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.3)

    yield

    server.should_exit = True


@pytest.fixture(scope="session")
def officer_session():
    """Create a persistent officer login session for testing."""
    login_data = login_officer_headless("anjali", "dev", resource_url=OFFICER_MCP_URL, base_url=PORTAL_URL)
    return {
        "officer": "anjali",
        "token": login_data["access_token"]
    }


def create_pending_application_fixture(block: str = "Sonari", applicant_name: str = "Pending Test Citizen", bank_account: str = None) -> dict:
    """Helper to create a fresh pending application for officer testing."""
    mobile = f"98{random.randint(10000000, 99999999)}"
    acc = bank_account or f"55{random.randint(1000000000, 9999999999)}"

    # 1. Save draft
    r1 = requests.post(
        f"{PORTAL_URL}/internal/v1/citizen/draft",
        headers={"X-Internal-Service-Key": INTERNAL_API_KEY, "X-Subject": f"citizen:{mobile}"},
        json={
            "applicant_name": applicant_name,
            "dob": "15/05/1958",
            "gender": "Female",
            "marital_status": "Widowed",
            "block": block,
            "village": f"{block} Central",
            "bank_account": acc,
            "ifsc": "SBIN0001234"
        },
        timeout=5
    )
    assert r1.status_code == 200

    # 2. Upload document
    r2 = requests.post(
        f"{PORTAL_URL}/internal/v1/citizen/upload_link",
        headers={"X-Internal-Service-Key": INTERNAL_API_KEY, "X-Subject": f"citizen:{mobile}"},
        timeout=5
    )
    assert r2.status_code == 200
    upload_url = r2.json()["upload_url"]
    fake_doc = b"%PDF-1.4 test certificate for pending fixture"
    requests.post(upload_url, files={"document": ("test_doc.pdf", fake_doc, "application/pdf")}, timeout=5)

    # 3. Submit
    r3 = requests.post(
        f"{PORTAL_URL}/internal/v1/citizen/submit",
        headers={"X-Internal-Service-Key": INTERNAL_API_KEY, "X-Subject": f"citizen:{mobile}"},
        json={"client_name": "Test Suite Fixture"},
        timeout=5
    )
    assert r3.status_code in (200, 201)
    data = r3.json()
    return {
        "mobile": mobile,
        "application_no": data["application_no"],
        "application_id": data.get("application_id"),
        "bank_account": acc
    }


def test_gate1_officer_my_queue(officer_session):
    """Officer can retrieve pending applications for assigned block (Sonari)."""
    # Create at least one fresh application in Sonari
    fixture = create_pending_application_fixture(block="Sonari", applicant_name="Sonari Queue Senior")

    client = MCPClientSession(OFFICER_MCP_URL, officer_session["token"])
    res = client.call_tool("my_queue")
    assert res.get("status") == "success"
    assert res.get("block") == "Sonari"
    cases = res.get("cases", [])
    assert len(cases) > 0
    # Verify our fixture application is in queue
    app_nos = [c["application_no"] for c in cases]
    assert fixture["application_no"] in app_nos


def test_gate2_officer_overdue_summary(officer_session):
    """Officer can get statutory SLA and overdue summary."""
    client = MCPClientSession(OFFICER_MCP_URL, officer_session["token"])
    res = client.call_tool("overdue_summary")
    assert res.get("status") == "success"
    assert res.get("sla_days") == 15
    assert "total_pending" in res
    assert "total_overdue" in res
    assert "blocks" in res
    assert "statutory_note" in res
    assert "Purvanchal Right to Public Services Act" in res.get("statutory_note", "")


def test_gate3_officer_view_case_with_flags(officer_session):
    """Officer can view full case dossier including duplicate bank warnings."""
    # Create two applications sharing the SAME bank account to trigger SHARED_BANK_ACCOUNT flag
    shared_acc = f"88{random.randint(1000000000, 9999999999)}"
    fix1 = create_pending_application_fixture(block="Sonari", applicant_name="First Senior", bank_account=shared_acc)
    fix2 = create_pending_application_fixture(block="Sonari", applicant_name="Second Senior", bank_account=shared_acc)

    client = MCPClientSession(OFFICER_MCP_URL, officer_session["token"])
    res = client.call_tool("view_case", {"application_no": fix2["application_no"]})
    assert res.get("status") == "success"
    assert res.get("application_no") == fix2["application_no"]
    assert res.get("applicant_name") == "Second Senior"
    assert res.get("is_decidable") is True

    # Check for SHARED_BANK_ACCOUNT review flag
    flags = res.get("flags", [])
    flag_types = [f.get("flag") for f in flags]
    assert "SHARED_BANK_ACCOUNT" in flag_types

    # Check audit trail has submission record
    audit = res.get("audit_trail", [])
    actions = [a.get("action") for a in audit]
    assert "SUBMIT" in actions


def test_gate4_officer_approve_case(officer_session):
    """Officer can approve a case with named audit logging and idempotence."""
    fix = create_pending_application_fixture(block="Sonari", applicant_name="Approve Test Senior")
    app_no = fix["application_no"]

    client = MCPClientSession(OFFICER_MCP_URL, officer_session["token"])

    # 1. Approve
    r_app = client.call_tool("approve_case", {"application_no": app_no, "remarks": "Age proof verified cleanly"})
    assert r_app.get("status") == "success"
    assert r_app.get("decision") == "APPROVED"
    assert r_app.get("decided_by") == "anjali"

    # 2. View case to verify status and audit row
    r_view = client.call_tool("view_case", {"application_no": app_no})
    assert r_view.get("status") == "success"
    assert r_view.get("application_status") == "APPROVED"
    assert r_view.get("is_decidable") is False
    audit_actors = [a.get("actor") for a in r_view.get("audit_trail", [])]
    assert "officer:anjali" in audit_actors

    # 3. Idempotent re-approval does not fail
    r_dup = client.call_tool("approve_case", {"application_no": app_no})
    assert r_dup.get("status") == "success"


def test_gate5_officer_reject_case_requires_reason(officer_session):
    """Rejection requires mandatory reason and records justification in audit log."""
    fix = create_pending_application_fixture(block="Sonari", applicant_name="Reject Test Senior")
    app_no = fix["application_no"]

    client = MCPClientSession(OFFICER_MCP_URL, officer_session["token"])

    # 1. Empty reason rejected
    r_empty = client.call_tool("reject_case", {"application_no": app_no, "reason": ""})
    assert r_empty.get("status") == "error"
    assert r_empty.get("error_code") == "reason_required"

    # 2. Rejection with valid justification
    justification = "Age proof certificate is unreadable and applicant age could not be confirmed"
    r_rej = client.call_tool("reject_case", {"application_no": app_no, "reason": justification})
    assert r_rej.get("status") == "success"
    assert r_rej.get("decision") == "REJECTED"
    assert r_rej.get("decided_by") == "anjali"

    # 3. View case to verify rejection and audit note
    r_view = client.call_tool("view_case", {"application_no": app_no})
    assert r_view.get("status") == "success"
    assert r_view.get("application_status") == "REJECTED"
    audit = r_view.get("audit_trail", [])
    reject_notes = [a.get("note") for a in audit if a.get("action") == "REJECTED"]
    assert any(justification in (n or "") for n in reject_notes)

