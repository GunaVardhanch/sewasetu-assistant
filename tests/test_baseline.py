import re
import time
import base64
import hashlib
import secrets
from urllib.parse import urlparse, parse_qs
import requests
import pytest

BASE_URL = "http://localhost:8000"


def test_public_pages():
    """Verify /, /about are reachable and render correctly."""
    resp_index = requests.get(f"{BASE_URL}/", timeout=10)
    assert resp_index.status_code == 200
    assert "Sewa Setu" in resp_index.text

    resp_about = requests.get(f"{BASE_URL}/about", timeout=10)
    assert resp_about.status_code == 200
    assert "Old Age Pension Scheme" in resp_about.text or "Sewa Setu" in resp_about.text


def test_admin_login():
    """Verify departmental sign in at /admin with ADMIN_PASSWORD=dev."""
    session = requests.Session()
    resp = session.post(
        f"{BASE_URL}/admin",
        data={"username": "admin", "password": "dev"},
        allow_redirects=True,
        timeout=10,
    )
    assert resp.status_code == 200
    assert "/admin/dashboard" in resp.url or "Departmental Dashboard" in resp.text


def test_gateway_otp():
    """Verify citizen OTP generation via OAuth login and retrieval from /__gateway/api/messages."""
    test_mobile = "9876543210"
    session = requests.Session()

    # 1. Register a public client
    reg_resp = session.post(
        f"{BASE_URL}/oauth/register",
        json={
            "client_name": "Baseline Test Client",
            "redirect_uris": ["http://localhost/callback"],
            "token_endpoint_auth_method": "none",
        },
        timeout=10,
    )
    assert reg_resp.status_code == 201
    client_id = reg_resp.json()["client_id"]

    # 2. Start authorization with PKCE
    verifier = secrets.token_urlsafe(32)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode("ascii")

    auth_resp = session.get(
        f"{BASE_URL}/oauth/authorize",
        params={
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": "http://localhost/callback",
            "scope": "citizen",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
        allow_redirects=False,
        timeout=10,
    )
    assert auth_resp.status_code == 302
    login_url = auth_resp.headers["Location"]
    parsed = urlparse(login_url)
    rid = parse_qs(parsed.query)["rid"][0]

    # 3. Post mobile to trigger OTP SMS
    login_post = session.post(
        f"{BASE_URL}/oauth/login",
        params={"rid": rid},
        data={"mobile": test_mobile},
        timeout=10,
    )
    assert login_post.status_code == 200

    # 4. Wait for simulated carrier delivery (1-4 seconds)
    time.sleep(4)

    # 5. Read from /__gateway/api/messages?to=<mobile>
    msg_resp = session.get(f"{BASE_URL}/__gateway/api/messages?to={test_mobile}", timeout=10)
    assert msg_resp.status_code == 200
    data = msg_resp.json()
    assert "messages" in data
    messages = [m for m in data["messages"] if m.get("to") == test_mobile]
    assert len(messages) > 0
    latest = messages[-1]
    assert latest.get("delivered") is True
    assert "Your Sewa Setu OTP is" in (latest.get("text") or "")


def test_full_web_application_submission():
    """Verify that a full citizen application submitted via the portal creates a live record."""
    test_mobile = "9876540001"
    session = requests.Session()

    # Step 0: Get /apply and solve captcha
    get_apply = session.get(f"{BASE_URL}/apply", timeout=10)
    assert get_apply.status_code == 200
    # Solve captcha: e.g. "Security check: 3 + 5"
    match = re.search(r"(\d+)\s*\+\s*(\d+)", get_apply.text)
    assert match is not None
    captcha_ans = int(match.group(1)) + int(match.group(2))

    # Submit mobile and captcha
    post_apply = session.post(
        f"{BASE_URL}/apply",
        data={"mobile": test_mobile, "captcha": str(captcha_ans)},
        allow_redirects=True,
        timeout=10,
    )
    assert post_apply.status_code == 200
    assert "/verify" in post_apply.url

    # Wait for OTP
    time.sleep(4)
    msg_resp = session.get(f"{BASE_URL}/__gateway/api/messages?to={test_mobile}", timeout=10)
    assert msg_resp.status_code == 200
    otp_text = msg_resp.json()["messages"][-1]["text"]
    otp_code = re.search(r"\b(\d{6})\b", otp_text).group(1)

    # Verify OTP
    post_verify = session.post(
        f"{BASE_URL}/verify",
        data={"otp": otp_code},
        allow_redirects=True,
        timeout=10,
    )
    assert post_verify.status_code == 200
    assert "/form/1" in post_verify.url

    # Step 1: Personal details
    post_s1 = session.post(
        f"{BASE_URL}/form/1",
        data={
            "applicant_name": "Kamala Borah",
            "dob": "01/01/1954",
            "gender": "FEMALE",
            "marital_status": "WIDOWED",
        },
        allow_redirects=True,
        timeout=10,
    )
    assert post_s1.status_code == 200
    assert "/form/2" in post_s1.url

    # Step 2: Address
    post_s2 = session.post(
        f"{BASE_URL}/form/2",
        data={
            "village": "Lakhipur",
            "block": "Sonari",
            "husband_name": "Late Biren Borah",
        },
        allow_redirects=True,
        timeout=10,
    )
    assert post_s2.status_code == 200
    assert "/form/3" in post_s2.url

    # Step 3: Bank
    post_s3 = session.post(
        f"{BASE_URL}/form/3",
        data={
            "bank_account": "123456789012",
            "ifsc": "SBIN0003077",
        },
        allow_redirects=True,
        timeout=10,
    )
    assert post_s3.status_code == 200
    assert "/upload" in post_s3.url

    # Step 4: Upload age proof
    dummy_pdf = b"%PDF-1.4 mock age proof document for automated baseline test"
    post_upload = session.post(
        f"{BASE_URL}/upload",
        files={"document": ("age_proof.pdf", dummy_pdf, "application/pdf")},
        allow_redirects=True,
        timeout=10,
    )
    assert post_upload.status_code == 200
    assert "/declaration" in post_upload.url

    # Step 5: Declaration & commit
    post_decl = session.post(
        f"{BASE_URL}/declaration",
        data={"confirm": "yes"},
        allow_redirects=True,
        timeout=10,
    )
    assert post_decl.status_code == 200
    assert "Application Submitted" in post_decl.text or "SSP" in post_decl.text

    # Extract application number
    app_no_match = re.search(r"SSP\d+", post_decl.text)
    assert app_no_match is not None
    app_no = app_no_match.group(0)

    # Step 6: Verify in /admin list
    admin_sess = requests.Session()
    admin_sess.post(
        f"{BASE_URL}/admin",
        data={"username": "admin", "password": "dev"},
        allow_redirects=True,
        timeout=10,
    )
    admin_list = admin_sess.get(f"{BASE_URL}/admin/applications?mobile={test_mobile}", timeout=10)
    assert admin_list.status_code == 200
    assert app_no in admin_list.text
    assert "Kamala Borah" in admin_list.text
    assert "PENDING" in admin_list.text
