# -*- coding: utf-8 -*-
"""
Phase 2 Test Suite: Shared Auth, MCP Skeletons & RFC 9728 / RFC 8707 Enforcement.

Gates verified:
  1. Unauthenticated request to /mcp/citizen returns 401 with WWW-Authenticate & resource_metadata
  2. Protected Resource Metadata endpoint (RFC 9728) returns valid metadata
  3. Citizen headless OAuth 2.1 flow succeeds and ping tool accepts valid token
  4. Officer headless OAuth 2.1 flow succeeds and ping tool accepts valid token
  5. Scope Isolation (RFC 6749): Citizen token against officer endpoint returns 403 Forbidden
  6. Scope Isolation (RFC 6749): Officer token against citizen endpoint returns 403 Forbidden
  7. Audience Enforcement (RFC 8707): Token issued for portal root rejected
  8. Revoked / Ended Session: Revoked session grant rejected with 401
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
from mcp_officer.server import app as officer_app
from evals.oauth_login import login_citizen_headless, login_officer_headless

PORTAL_URL = "http://localhost:8000"
CITIZEN_MCP_URL = "http://localhost:8001/mcp/citizen"
OFFICER_MCP_URL = "http://localhost:8002/mcp/officer"
CITIZEN_BASE = "http://localhost:8001"
OFFICER_BASE = "http://localhost:8002"


def parse_mcp_response(resp: requests.Response) -> dict:
    """Parse either raw JSON or SSE event stream returned by streamable HTTP."""
    text = resp.text
    if "data:" in text:
        for line in text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
    return resp.json()


@pytest.fixture(scope="session", autouse=True)
def run_mcp_servers():
    """Start citizen and officer MCP servers in background threads during test session."""
    os.environ["PORTAL_INTERNAL_URL"] = PORTAL_URL
    os.environ["PUBLIC_BASE_URL"] = PORTAL_URL
    os.environ["CITIZEN_RESOURCE_URL"] = CITIZEN_MCP_URL
    os.environ["OFFICER_RESOURCE_URL"] = OFFICER_MCP_URL

    cfg_cit = uvicorn.Config(citizen_app, host="127.0.0.1", port=8001, log_level="warning")
    server_cit = uvicorn.Server(cfg_cit)
    t_cit = threading.Thread(target=server_cit.run, daemon=True)
    t_cit.start()

    cfg_off = uvicorn.Config(officer_app, host="127.0.0.1", port=8002, log_level="warning")
    server_off = uvicorn.Server(cfg_off)
    t_off = threading.Thread(target=server_off.run, daemon=True)
    t_off.start()

    # Wait for servers to bind
    for _ in range(20):
        try:
            r1 = requests.get(f"{CITIZEN_BASE}/healthz", timeout=1)
            r2 = requests.get(f"{OFFICER_BASE}/healthz", timeout=1)
            if r1.status_code == 200 and r2.status_code == 200:
                break
        except Exception:
            time.sleep(0.3)

    yield

    server_cit.should_exit = True
    server_off.should_exit = True


def test_gate1_unauthenticated_requests_return_401():
    """Missing Authorization header must return 401 with WWW-Authenticate."""
    # Citizen endpoint
    resp = requests.post(CITIZEN_MCP_URL, json={"jsonrpc": "2.0", "id": 1, "method": "ping"}, timeout=5)
    assert resp.status_code == 401
    assert "www-authenticate" in resp.headers
    www_auth = resp.headers["www-authenticate"]
    assert "Bearer" in www_auth
    assert "resource_metadata" in www_auth

    # Officer endpoint
    resp_off = requests.post(OFFICER_MCP_URL, json={"jsonrpc": "2.0", "id": 1, "method": "ping"}, timeout=5)
    assert resp_off.status_code == 401
    assert "www-authenticate" in resp_off.headers
    assert "Bearer" in resp_off.headers["www-authenticate"]


def test_gate2_rfc9728_protected_resource_metadata():
    """RFC 9728 protected resource metadata documents must be available."""
    # Citizen metadata
    r1 = requests.get(f"{CITIZEN_BASE}/.well-known/oauth-protected-resource", timeout=5)
    assert r1.status_code == 200
    meta1 = r1.json()
    assert meta1["resource"] == CITIZEN_MCP_URL
    assert meta1["scopes_supported"] == ["citizen"]
    assert PORTAL_URL in meta1["authorization_servers"]

    # Officer metadata
    r2 = requests.get(f"{OFFICER_BASE}/.well-known/oauth-protected-resource", timeout=5)
    assert r2.status_code == 200
    meta2 = r2.json()
    assert meta2["resource"] == OFFICER_MCP_URL
    assert meta2["scopes_supported"] == ["officer"]
    assert PORTAL_URL in meta2["authorization_servers"]


def test_gate3_citizen_oauth_flow_and_ping():
    """Citizen OAuth 2.1 login generates a valid RS256 token that passes authentication."""
    mobile = "9876543210"
    login_data = login_citizen_headless(mobile=mobile, resource_url=CITIZEN_MCP_URL, base_url=PORTAL_URL)
    access_token = login_data["access_token"]
    assert access_token

    # Initialize handshake
    headers = {
        "Authorization": f"Bearer {access_token}",
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
    r = requests.post(CITIZEN_MCP_URL, headers=headers, json=init_payload, timeout=5)
    assert r.status_code == 200
    data = parse_mcp_response(r)
    assert "result" in data
    assert data["result"]["serverInfo"]["name"] == "sewasetu-citizen"


def test_gate4_officer_oauth_flow_and_ping():
    """Officer OAuth 2.1 login generates a valid RS256 token that passes authentication."""
    login_data = login_officer_headless("anjali", "dev", resource_url=OFFICER_MCP_URL, base_url=PORTAL_URL)
    access_token = login_data["access_token"]
    assert access_token

    headers = {
        "Authorization": f"Bearer {access_token}",
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
    r = requests.post(OFFICER_MCP_URL, headers=headers, json=init_payload, timeout=5)
    assert r.status_code == 200
    data = parse_mcp_response(r)
    assert "result" in data
    assert data["result"]["serverInfo"]["name"] == "sewasetu-officer"


def test_gate5_scope_isolation_citizen_cannot_access_officer():
    """Citizen token sent to officer endpoint must be rejected with 403 Forbidden."""
    login_data = login_citizen_headless("9876543210", resource_url=OFFICER_MCP_URL, base_url=PORTAL_URL)
    citizen_token = login_data["access_token"]

    headers = {"Authorization": f"Bearer {citizen_token}"}
    r = requests.post(OFFICER_MCP_URL, headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "initialize"}, timeout=5)
    assert r.status_code == 403
    assert "insufficient_scope" in r.headers.get("www-authenticate", "") or "insufficient_scope" in r.text


def test_gate6_scope_isolation_officer_cannot_access_citizen():
    """Officer token sent to citizen endpoint must be rejected with 403 Forbidden."""
    login_data = login_officer_headless("anjali", "dev", resource_url=CITIZEN_MCP_URL, base_url=PORTAL_URL)
    officer_token = login_data["access_token"]

    headers = {"Authorization": f"Bearer {officer_token}"}
    r = requests.post(CITIZEN_MCP_URL, headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "initialize"}, timeout=5)
    assert r.status_code == 403
    assert "insufficient_scope" in r.headers.get("www-authenticate", "") or "insufficient_scope" in r.text


def test_gate7_audience_mismatch_rejected():
    """Token requested without resource indicator (or portal root aud) must be rejected with 401."""
    # Login asking for portal root audience
    login_data = login_citizen_headless("9876543210", resource_url=PORTAL_URL, base_url=PORTAL_URL)
    root_aud_token = login_data["access_token"]

    headers = {"Authorization": f"Bearer {root_aud_token}"}
    r = requests.post(CITIZEN_MCP_URL, headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "initialize"}, timeout=5)
    assert r.status_code == 401


def test_gate8_revoked_session_rejected():
    """Token whose session was ended in portal must be rejected with 401."""
    login_data = login_citizen_headless("9876543210", resource_url=CITIZEN_MCP_URL, base_url=PORTAL_URL)
    token = login_data["access_token"]

    # Verify works initially
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    r = requests.post(CITIZEN_MCP_URL, headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1.0"}}}, timeout=5)
    assert r.status_code == 200

    # End session via internal portal endpoint
    r_end = requests.post(
        f"{PORTAL_URL}/internal/v1/citizen/session_end",
        headers={"X-Internal-Service-Key": "dev-internal-key-2026", "X-Subject": "citizen:9876543210"},
        timeout=5
    )
    assert r_end.status_code == 200

    # Same token now rejected
    r_after = requests.post(CITIZEN_MCP_URL, headers=headers, json={"jsonrpc": "2.0", "id": 2, "method": "initialize"}, timeout=5)
    assert r_after.status_code == 401
