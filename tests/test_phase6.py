# -*- coding: utf-8 -*-
"""
Phase 6 Test Suite — Public Eval Dashboard (/eval-dashboard)
Verifies public dashboard page render, metrics cards, transcripts viewer, and JSON API.
"""

import requests

PORTAL_URL = "http://localhost:8000"


def test_eval_dashboard_html_page():
    """Verify /eval-dashboard renders full government portal UI with 18 personas."""
    resp = requests.get(f"{PORTAL_URL}/eval-dashboard", timeout=5)
    assert resp.status_code == 200
    html = resp.text

    # Check key dashboard sections
    assert "Sewa Setu" in html
    assert "Evaluation Dashboard" in html
    assert "100% INVARIANTS VERIFIED" in html
    assert "What the Personas Taught Us" in html

    # Verify personas are rendered
    assert "Bhaben Hazarika" in html
    assert "Kamala Devi" in html
    assert "Anjali Sharma" in html
    assert "C1" in html
    assert "O1" in html
    assert "badge-pass" in html


def test_eval_dashboard_json_api():
    """Verify /eval-dashboard/data returns valid telemetry JSON with 100% pass rate."""
    resp = requests.get(f"{PORTAL_URL}/eval-dashboard/data", timeout=5)
    assert resp.status_code == 200
    data = resp.json()

    # Check summary
    summary = data.get("summary", {})
    assert summary.get("total") == 18
    assert summary.get("passed") == 18
    assert summary.get("failed") == 0
    assert summary.get("pass_rate") == 100.0
    assert summary.get("citizen_count") == 12
    assert summary.get("officer_count") == 6

    # Check narrative key fixes
    narrative = data.get("narrative", {})
    assert len(narrative.get("key_fixes", [])) >= 5

    # Check persona list
    personas = data.get("personas", [])
    assert len(personas) == 18
    for p in personas:
        assert p.get("status") == "PASS"
        assert len(p.get("turns", [])) > 0
