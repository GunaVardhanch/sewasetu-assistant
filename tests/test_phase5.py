# -*- coding: utf-8 -*-
"""
Phase 5 Test Suite — Personas & Evals Suite (C1 to C12, O1 to O6)
Verifies 100% pass rate across all 18 personas with live PostgreSQL database verification.
"""

import os
import sys
import time
import pytest
import uvicorn
import requests
import threading

from mcp_citizen.server import create_citizen_app
from mcp_officer.server import create_officer_app
from evals.runner import run_all_evals

PORTAL_URL = "http://localhost:8000"
CITIZEN_MCP_URL = "http://localhost:8001/mcp/citizen"
OFFICER_MCP_URL = "http://localhost:8002/mcp/officer"

citizen_app = create_citizen_app()
officer_app = create_officer_app()


@pytest.fixture(scope="session", autouse=True)
def run_mcp_servers():
    """Start both citizen and officer MCP servers in background threads during test session."""
    os.environ["PORTAL_INTERNAL_URL"] = PORTAL_URL
    os.environ["PUBLIC_BASE_URL"] = PORTAL_URL
    os.environ["CITIZEN_RESOURCE_URL"] = CITIZEN_MCP_URL
    os.environ["OFFICER_RESOURCE_URL"] = OFFICER_MCP_URL

    cfg_cit = uvicorn.Config(citizen_app, host="127.0.0.1", port=8001, log_level="warning")
    srv_cit = uvicorn.Server(cfg_cit)
    t_cit = threading.Thread(target=srv_cit.run, daemon=True)
    t_cit.start()

    cfg_off = uvicorn.Config(officer_app, host="127.0.0.1", port=8002, log_level="warning")
    srv_off = uvicorn.Server(cfg_off)
    t_off = threading.Thread(target=srv_off.run, daemon=True)
    t_off.start()

    # Wait for both servers to report healthy
    for _ in range(25):
        try:
            r1 = requests.get("http://127.0.0.1:8001/healthz", timeout=1)
            r2 = requests.get("http://127.0.0.1:8002/healthz", timeout=1)
            if r1.status_code == 200 and r2.status_code == 200:
                break
        except Exception:
            time.sleep(0.3)

    yield

    srv_cit.should_exit = True
    srv_off.should_exit = True


def test_full_persona_eval_suite():
    """Run all 18 personas, verify 100% pass rate, and check DB invariant assertions."""
    eval_output = run_all_evals()

    summary = eval_output["summary"]
    personas = eval_output["personas"]

    assert summary["total"] == 18, f"Expected 18 personas, got {summary['total']}"
    assert summary["failed"] == 0, f"Personas failed: {[p['id'] for p in personas if p['status'] != 'PASS']}"
    assert summary["passed"] == 18, f"Only {summary['passed']} personas passed"
    assert summary["pass_rate"] == 100.0

    # Verify each persona passed
    for p in personas:
        assert p["status"] == "PASS", f"Persona {p['id']} ({p['name']}) failed: {p.get('error')}"
        assert len(p["turns"]) > 0, f"Persona {p['id']} has no recorded turns"

