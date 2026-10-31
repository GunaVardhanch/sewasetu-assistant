# -*- coding: utf-8 -*-
"""
Database & Invariant Verification Suite for Sewa Setu Evaluations.
Connects to portal's /internal/v1/eval/inspect to verify Postgres applications, audit_log, and drafts.
"""

import os
import requests
from typing import Dict, Any, List, Optional

PORTAL_URL = os.environ.get("PORTAL_INTERNAL_URL", "http://localhost:8000").rstrip("/")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "dev-internal-key-2026")


def _inspect_portal(mobile: Optional[str] = None, application_no: Optional[str] = None, application_id: Optional[int] = None) -> Dict[str, Any]:
    """Fetch live Postgres application, audit trail, and draft snapshot from portal."""
    params = {}
    if mobile:
        params["mobile"] = mobile
    if application_no:
        params["application_no"] = application_no
    if application_id:
        params["application_id"] = application_id

    headers = {"X-Internal-Service-Key": INTERNAL_API_KEY}
    resp = requests.get(f"{PORTAL_URL}/internal/v1/eval/inspect", headers=headers, params=params, timeout=5)
    if resp.status_code != 200:
        raise RuntimeError(f"Portal inspect failed ({resp.status_code}): {resp.text}")
    return resp.json()


def check_application_exists(
    mobile: Optional[str] = None,
    application_no: Optional[str] = None,
    expected_status: Optional[str] = None,
    expected_name: Optional[str] = None,
    expected_block: Optional[str] = None,
    expected_marital: Optional[str] = None,
    check_doc: bool = False
) -> Dict[str, Any]:
    """Verify application exists in Postgres with matching columns."""
    res = _inspect_portal(mobile=mobile, application_no=application_no)
    app = res.get("application")
    assert app is not None, f"Expected application for mobile={mobile} / app_no={application_no} to exist in DB, but found None"

    if expected_status:
        assert app.get("status") == expected_status, f"Application status {app.get('status')} != expected {expected_status}"
    if expected_name:
        assert app.get("applicant_name") == expected_name, f"Applicant name {app.get('applicant_name')} != expected {expected_name}"
    if expected_block:
        assert app.get("block") == expected_block, f"Block {app.get('block')} != expected {expected_block}"
    if expected_marital:
        assert app.get("marital_status") == expected_marital, f"Marital status {app.get('marital_status')} != expected {expected_marital}"
    if check_doc:
        assert app.get("has_document_file") is True, f"Application document file missing on disk"

    return app


def check_application_does_not_exist(mobile: str) -> bool:
    """Verify no application row exists for given mobile in Postgres."""
    res = _inspect_portal(mobile=mobile)
    app = res.get("application")
    assert app is None, f"Expected no application for mobile={mobile}, but found application_no={app.get('application_no')}"
    return True


def check_audit_trail(
    mobile: Optional[str] = None,
    application_no: Optional[str] = None,
    expected_actions: Optional[List[str]] = None,
    expected_actor: Optional[str] = None,
    expected_note_substring: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Verify actions recorded in PostgreSQL audit_log table."""
    res = _inspect_portal(mobile=mobile, application_no=application_no)
    audit = res.get("audit_trail", [])
    actions = [a.get("action") for a in audit]

    if expected_actions:
        for expected in expected_actions:
            assert expected in actions, f"Expected action '{expected}' in audit trail, but found {actions}"

    if expected_actor:
        actors = [a.get("actor") for a in audit]
        assert any(expected_actor in (act or "") for act in actors), f"Expected actor '{expected_actor}' in audit actors {actors}"

    if expected_note_substring:
        notes = [a.get("note") for a in audit]
        assert any(expected_note_substring in (n or "") for n in notes), f"Expected note containing '{expected_note_substring}' in audit notes {notes}"

    return audit


def check_draft_state(
    mobile: str,
    must_exist: bool = True,
    expected_name: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Verify state in agent_drafts Postgres table."""
    res = _inspect_portal(mobile=mobile)
    draft = res.get("draft")
    if not must_exist:
        return None
    assert draft is not None, f"Expected active draft for mobile={mobile}, but found None"
    if expected_name:
        data = draft.get("data", {})
        assert data.get("applicant_name") == expected_name, f"Draft name {data.get('applicant_name')} != expected {expected_name}"
    return draft

