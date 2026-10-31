import os
import re
import time
import base64
import hashlib
import secrets
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, parse_qs
import requests
import pytest

BASE_URL = "http://localhost:8000"
INTERNAL_API_KEY = "dev-internal-key-2026"
HEADERS_AUTH = {
    "X-Internal-Service-Key": INTERNAL_API_KEY
}


def test_scheme_info():
    """Verify live scheme info endpoint returns portal facts."""
    resp = requests.get(f"{BASE_URL}/internal/v1/citizen/scheme_info", headers=HEADERS_AUTH, timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert data["minimum_age"] == 60
    assert data["monthly_pension"] == "₹250 per month"
    assert data["sla_days"] == 15
    assert "Sonari" in data["blocks"]
    assert len(data["accepted_documents"]) >= 5


def test_eligibility_age_check():
    """Verify stateless age check on today's date."""
    # Underage (e.g. born in 1968, 58 years old)
    r_young = requests.post(
        f"{BASE_URL}/internal/v1/citizen/eligibility",
        headers=HEADERS_AUTH,
        json={"dob": "15/08/1968"},
        timeout=10,
    )
    assert r_young.status_code == 200
    d_young = r_young.json()
    assert d_young["eligible"] is False
    assert "turning_60_date" in d_young

    # Eligible (e.g. born in 1954, 72 years old)
    r_old = requests.post(
        f"{BASE_URL}/internal/v1/citizen/eligibility",
        headers=HEADERS_AUTH,
        json={"dob": "01/01/1954"},
        timeout=10,
    )
    assert r_old.status_code == 200
    assert r_old.json()["eligible"] is True

    # Future date rejected
    r_future = requests.post(
        f"{BASE_URL}/internal/v1/citizen/eligibility",
        headers=HEADERS_AUTH,
        json={"dob": "01/01/2030"},
        timeout=10,
    )
    assert r_future.status_code == 400
    assert "future" in r_future.json()["error"].lower()


def test_validation_parity_between_web_and_api():
    """Gate 1: Web-form application and API application with same bad data reject with same error text."""
    test_mobile = f"98{secrets.randbelow(100000000):08d}"
    bad_data = {
        "applicant_name": "A",  # Name too short
        "dob": "15/08/1975",    # Under 60
        "gender": "",           # Missing gender
        "marital_status": "",   # Missing marital status
        "village": "",          # Missing village
        "block": "UnknownBlock",# Invalid block
        "bank_account": "123",  # Short bank account
        "ifsc": "INVALID_IFSC", # Invalid IFSC
    }

    # 1. Test via internal API draft save / submit
    headers = dict(HEADERS_AUTH)
    headers["X-Subject"] = f"citizen:{test_mobile}"

    save_resp = requests.post(
        f"{BASE_URL}/internal/v1/citizen/draft",
        headers=headers,
        json=bad_data,
        timeout=10,
    )
    assert save_resp.status_code == 200
    api_errors = save_resp.json()["validation_errors"]

    # 2. Test via web declaration preview
    session = requests.Session()
    # Mock session state for web declaration preview
    # By hitting /apply, /verify, then setting form data
    get_apply = session.get(f"{BASE_URL}/apply", timeout=10)
    match = re.search(r"(\d+)\s*\+\s*(\d+)", get_apply.text)
    captcha_ans = int(match.group(1)) + int(match.group(2))
    session.post(
        f"{BASE_URL}/apply",
        data={"mobile": test_mobile, "captcha": str(captcha_ans)},
        timeout=10,
    )
    otp_code = wait_for_otp(session, test_mobile)
    session.post(f"{BASE_URL}/verify", data={"otp": otp_code}, timeout=10)

    # Post bad data across form steps
    session.post(f"{BASE_URL}/form/1", data={
        "applicant_name": bad_data["applicant_name"],
        "dob": bad_data["dob"],
        "gender": bad_data["gender"],
        "marital_status": bad_data["marital_status"]
    }, timeout=10)
    session.post(f"{BASE_URL}/form/2", data={
        "village": bad_data["village"],
        "block": bad_data["block"]
    }, timeout=10)
    session.post(f"{BASE_URL}/form/3", data={
        "bank_account": bad_data["bank_account"],
        "ifsc": bad_data["ifsc"]
    }, timeout=10)

    # Preview on /declaration
    decl_resp = session.get(f"{BASE_URL}/declaration", timeout=10)
    assert decl_resp.status_code == 200
    # Every error returned by API must be present in web declaration preview
    for err in api_errors:
        assert err in decl_resp.text, f"Expected '{err}' to appear on web declaration preview"


def test_concurrency_parallel_submits():
    """Gate 2: Two parallel submits for one mobile produce exactly one active row."""
    test_mobile = f"98{secrets.randbelow(100000000):08d}"
    headers = dict(HEADERS_AUTH)
    headers["X-Subject"] = f"citizen:{test_mobile}"

    # 1. Setup valid draft details
    valid_data = {
        "applicant_name": "Kamala Borah",
        "dob": "01/01/1954",
        "gender": "Female",
        "marital_status": "Widowed",
        "husband_name": "Biren Borah",
        "village": "Lakhipur",
        "block": "Sonari",
        "bank_account": "123456789012",
        "ifsc": "SBIN0003077",
    }
    requests.post(f"{BASE_URL}/internal/v1/citizen/draft", headers=headers, json=valid_data, timeout=10)

    # 2. Get upload link and upload valid age proof doc
    link_resp = requests.post(f"{BASE_URL}/internal/v1/citizen/upload_link", headers=headers, timeout=10)
    upload_url = link_resp.json()["upload_url"]

    dummy_pdf = b"%PDF-1.4 mock age proof document for concurrency test"
    up_resp = requests.post(upload_url, files={"document": ("proof.pdf", dummy_pdf, "application/pdf")}, timeout=10)
    assert up_resp.status_code == 200

    # 3. Fire two parallel submits concurrently
    def call_submit():
        return requests.post(f"{BASE_URL}/internal/v1/citizen/submit", headers=headers, json={"client_name": "ConcurrentTester"}, timeout=15)

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(call_submit)
        f2 = executor.submit(call_submit)
        r1 = f1.result()
        r2 = f2.result()

    statuses = [r1.status_code, r2.status_code]
    assert 201 in statuses, "At least one submission must succeed with 201 Created"
    
    # Both should have the same application_no
    app_no1 = r1.json().get("application_no")
    app_no2 = r2.json().get("application_no")
    assert app_no1 == app_no2
    assert (r1.json().get("status") == "submitted" and r2.json().get("status") == "already_submitted") or \
           (r2.json().get("status") == "submitted" and r1.json().get("status") == "already_submitted")


def test_bi_directional_visibility():
    """Gate 3: An API-created application shows up at /status and /admin; a web application shows up in API status."""
    # Part A: Create via API
    test_mobile_api = f"98{secrets.randbelow(100000000):08d}"
    headers_api = dict(HEADERS_AUTH)
    headers_api["X-Subject"] = f"citizen:{test_mobile_api}"

    data_api = {
        "applicant_name": "Phul Mati Chetia",
        "dob": "03/03/1958",
        "gender": "Female",
        "marital_status": "Married",
        "village": "Nalbari Gaon",
        "block": "Dhemaji Pathar",
        "bank_account": "987654321098",
        "ifsc": "SBIN0003077",
    }
    requests.post(f"{BASE_URL}/internal/v1/citizen/draft", headers=headers_api, json=data_api, timeout=10)
    link_resp = requests.post(f"{BASE_URL}/internal/v1/citizen/upload_link", headers=headers_api, timeout=10)
    upload_url = link_resp.json()["upload_url"]
    dummy_pdf = b"%PDF-1.4 test document"
    requests.post(upload_url, files={"document": ("proof.pdf", dummy_pdf, "application/pdf")}, timeout=10)

    sub_resp = requests.post(f"{BASE_URL}/internal/v1/citizen/submit", headers=headers_api, json={"client_name": "BiDirectionalTest"}, timeout=10)
    assert sub_resp.status_code == 201
    app_no = sub_resp.json()["application_no"]

    # Verify at /status portal with DOB password (03031958)
    status_sess = requests.Session()
    login_resp = status_sess.post(
        f"{BASE_URL}/status",
        data={"mobile": test_mobile_api, "password": "03031958"},
        allow_redirects=True,
        timeout=10,
    )
    assert login_resp.status_code == 200
    assert app_no in login_resp.text
    assert "Phul Mati Chetia" in login_resp.text

    # Verify at /admin
    admin_sess = requests.Session()
    admin_sess.post(f"{BASE_URL}/admin", data={"username": "admin", "password": "dev"}, timeout=10)
    admin_view = admin_sess.get(f"{BASE_URL}/admin/applications?mobile={test_mobile_api}", timeout=10)
    assert admin_view.status_code == 200
    assert app_no in admin_view.text


def test_officer_decide_idempotence_and_audit():
    """Gate 4: Decide on non-PENDING row changes nothing and writes no audit row. Reject requires reason."""
    test_mobile = f"98{secrets.randbelow(100000000):08d}"
    headers_cit = dict(HEADERS_AUTH)
    headers_cit["X-Subject"] = f"citizen:{test_mobile}"

    # Create application
    requests.post(f"{BASE_URL}/internal/v1/citizen/draft", headers=headers_cit, json={
        "applicant_name": "Dulal Hazarika",
        "dob": "01/01/1954",
        "gender": "Male",
        "marital_status": "Married",
        "village": "Namti Chariali",
        "block": "Namti",
        "bank_account": "112233445566",
        "ifsc": "SBIN0003077",
    }, timeout=10)
    l_resp = requests.post(f"{BASE_URL}/internal/v1/citizen/upload_link", headers=headers_cit, timeout=10)
    requests.post(l_resp.json()["upload_url"], files={"document": ("doc.pdf", b"%PDF-1.4 test", "application/pdf")}, timeout=10)
    sub = requests.post(f"{BASE_URL}/internal/v1/citizen/submit", headers=headers_cit, timeout=10)
    app_id = sub.json()["application_id"]

    # 1. Officer Anjali rejects with empty reason -> must fail
    headers_off = dict(HEADERS_AUTH)
    headers_off["X-Subject"] = "officer:anjali"
    rej_bad = requests.post(
        f"{BASE_URL}/internal/v1/officer/decide",
        headers=headers_off,
        json={"application_id": app_id, "decision": "REJECTED", "reason": ""},
        timeout=10,
    )
    assert rej_bad.status_code == 400
    assert "reason is required" in rej_bad.json()["message"].lower()

    # 2. Officer Anjali approves
    app_ok = requests.post(
        f"{BASE_URL}/internal/v1/officer/decide",
        headers=headers_off,
        json={"application_id": app_id, "decision": "APPROVED", "note": "Verified genuine age proof."},
        timeout=10,
    )
    assert app_ok.status_code == 200
    assert app_ok.json()["status"] == "success"
    assert app_ok.json()["decided_by"] == "anjali"

    # 3. View case via officer API -> verify audit trail has officer:anjali
    case_resp = requests.get(f"{BASE_URL}/internal/v1/officer/case/{app_id}", headers=headers_off, timeout=10)
    assert case_resp.status_code == 200
    case_data = case_resp.json()
    assert case_data["status"] == "APPROVED"
    assert case_data["decided_by"] == "anjali"
    audit_actors = [a["actor"] for a in case_data["audit_trail"]]
    assert "officer:anjali" in audit_actors
    initial_audit_len = len(case_data["audit_trail"])

    # 4. Attempt to decide again (idempotence)
    second_decide = requests.post(
        f"{BASE_URL}/internal/v1/officer/decide",
        headers=headers_off,
        json={"application_id": app_id, "decision": "REJECTED", "reason": "Attempting double decision"},
        timeout=10,
    )
    assert second_decide.status_code == 200
    assert second_decide.json()["status"] == "already_decided"

    # Verify audit trail count did NOT increase
    case_resp2 = requests.get(f"{BASE_URL}/internal/v1/officer/case/{app_id}", headers=headers_off, timeout=10)
    assert len(case_resp2.json()["audit_trail"]) == initial_audit_len


def wait_for_otp(session, mobile, timeout_sec=8):
    """Poll SMS gateway until carrier delivers the OTP message."""
    start = time.time()
    while time.time() - start < timeout_sec:
        time.sleep(1)
        r = session.get(f"{BASE_URL}/__gateway/api/messages?to={mobile}", timeout=5)
        if r.status_code == 200:
            msgs = r.json().get("messages", [])
            for m in reversed(msgs):
                if m.get("delivered") and m.get("text"):
                    match = re.search(r"\b(\d{6})\b", m["text"])
                    if match:
                        return match.group(1)
    raise TimeoutError(f"OTP for {mobile} not delivered within {timeout_sec} seconds")


def test_session_check_and_revocation():
    """Gate 5: An ended grant makes the session check fail."""
    test_mobile = f"98{secrets.randbelow(100000000):08d}"
    session = requests.Session()

    # Register client and login
    reg_resp = session.post(f"{BASE_URL}/oauth/register", json={
        "client_name": "SessionCheckClient",
        "redirect_uris": ["http://localhost/callback"],
        "token_endpoint_auth_method": "none"
    }, timeout=10)
    client_id = reg_resp.json()["client_id"]

    verifier = secrets.token_urlsafe(32)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode("ascii")

    auth_resp = session.get(f"{BASE_URL}/oauth/authorize", params={
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": "http://localhost/callback",
        "scope": "citizen",
        "code_challenge": challenge,
        "code_challenge_method": "S256"
    }, allow_redirects=False, timeout=10)
    rid = parse_qs(urlparse(auth_resp.headers["Location"]).query)["rid"][0]

    session.post(f"{BASE_URL}/oauth/login", params={"rid": rid}, data={"mobile": test_mobile}, timeout=10)
    otp_code = wait_for_otp(session, test_mobile)

    # Submit OTP and consent
    session.post(f"{BASE_URL}/oauth/login", params={"rid": rid}, data={"otp": otp_code}, allow_redirects=False, timeout=10)
    consent_resp = session.post(f"{BASE_URL}/oauth/consent", params={"rid": rid}, data={"decision": "allow"}, allow_redirects=False, timeout=10)
    assert consent_resp.status_code == 302
    assert "Location" in consent_resp.headers
    code = parse_qs(urlparse(consent_resp.headers["Location"]).query)["code"][0]

    # Exchange code for token
    token_resp = session.post(f"{BASE_URL}/oauth/token", data={
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "code_verifier": verifier,
        "redirect_uri": "http://localhost/callback"
    }, timeout=10)
    assert token_resp.status_code == 200

    # 1. Session check should be valid
    subject = f"citizen:{test_mobile}"
    chk1 = requests.get(f"{BASE_URL}/internal/v1/session_check?sub={subject}&client_id={client_id}", headers=HEADERS_AUTH, timeout=10)
    assert chk1.status_code == 200
    assert chk1.json()["valid"] is True

    # 2. End session via citizen session_end
    end_resp = requests.post(
        f"{BASE_URL}/internal/v1/citizen/session_end",
        headers={"X-Internal-Service-Key": INTERNAL_API_KEY, "X-Subject": subject},
        timeout=10,
    )
    assert end_resp.status_code == 200
    assert end_resp.json()["status"] == "signed_out"

    # 3. Session check must now fail
    chk2 = requests.get(f"{BASE_URL}/internal/v1/session_check?sub={subject}&client_id={client_id}", headers=HEADERS_AUTH, timeout=10)
    assert chk2.status_code == 200
    assert chk2.json()["valid"] is False

