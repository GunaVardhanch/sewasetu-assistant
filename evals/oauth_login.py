# -*- coding: utf-8 -*-
"""
Headless OAuth 2.1 client for Sewa Setu evaluations and automated testing.
Performs RFC 7591 DCR, PKCE S256, SMS gateway OTP retrieval, consent, and token exchange.
"""

import time
import base64
import hashlib
import secrets
from urllib.parse import urlparse, parse_qs
from typing import Dict, Any, Optional, Tuple
import requests
import jwt

GATEWAY_POLL_TIMEOUT = 10.0


class OAuthLoginError(Exception):
    pass


def _generate_pkce() -> Tuple[str, str]:
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def get_latest_message_id(session: requests.Session, base_url: str, mobile: str) -> int:
    """Get the highest message ID currently present for the given mobile."""
    gw_url = f"{base_url}/__gateway/api/messages?to={mobile}"
    try:
        r = session.get(gw_url, timeout=5)
        if r.status_code == 200:
            messages = r.json().get("messages", [])
            ids = [m.get("id", 0) for m in messages if isinstance(m.get("id"), int)]
            return max(ids) if ids else 0
    except Exception:
        pass
    return 0


def wait_for_otp(session: requests.Session, base_url: str, mobile: str, since_id: int = 0, timeout: float = GATEWAY_POLL_TIMEOUT) -> str:
    """Poll simulated telecom gateway until a new SMS (id > since_id) is delivered."""
    start = time.time()
    gw_url = f"{base_url}/__gateway/api/messages?to={mobile}"
    while time.time() - start < timeout:
        time.sleep(1.0)
        try:
            r = session.get(gw_url, timeout=5)
            if r.status_code == 200:
                messages = r.json().get("messages", [])
                for m in reversed(messages):
                    if m.get("delivered") and m.get("text") and m.get("id", 0) > since_id:
                        import re
                        match = re.search(r"\b(\d{6})\b", m["text"])
                        if match:
                            return match.group(1)
        except Exception:
            pass
    raise OAuthLoginError(f"New OTP for mobile {mobile} (since_id {since_id}) was not delivered by carrier within {timeout}s")


def login_citizen_headless(
    mobile: str,
    resource_url: str,
    base_url: str = "http://localhost:8000",
    client_name: str = "Citizen Eval Client"
) -> Dict[str, Any]:
    """Complete citizen headless OAuth flow: DCR -> Authorize -> OTP -> Consent -> Token."""
    session = requests.Session()

    # 1. Dynamic Client Registration (RFC 7591)
    reg_resp = session.post(
        f"{base_url}/oauth/register",
        json={
            "client_name": client_name,
            "redirect_uris": ["http://localhost/callback"],
            "token_endpoint_auth_method": "none",
        },
        timeout=10,
    )
    if reg_resp.status_code != 201:
        raise OAuthLoginError(f"DCR failed ({reg_resp.status_code}): {reg_resp.text}")
    client_id = reg_resp.json()["client_id"]

    # 2. Authorization Request with PKCE & RFC 8707 Resource Indicator
    verifier, challenge = _generate_pkce()
    auth_resp = session.get(
        f"{base_url}/oauth/authorize",
        params={
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": "http://localhost/callback",
            "scope": "citizen",
            "resource": resource_url,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
        allow_redirects=False,
        timeout=10,
    )
    if auth_resp.status_code != 302 or "Location" not in auth_resp.headers:
        raise OAuthLoginError(f"Authorize failed ({auth_resp.status_code}): {auth_resp.text}")

    login_loc = auth_resp.headers["Location"]
    rid = parse_qs(urlparse(login_loc).query)["rid"][0]

    # 3. Post mobile to trigger OTP SMS
    since_id = get_latest_message_id(session, base_url, mobile)
    mob_resp = session.post(
        f"{base_url}/oauth/login",
        params={"rid": rid},
        data={"mobile": mobile},
        timeout=10,
    )
    if mob_resp.status_code != 200:
        raise OAuthLoginError(f"Login mobile submit failed ({mob_resp.status_code})")

    # 4. Read OTP from simulated SMS gateway
    otp = wait_for_otp(session, base_url, mobile, since_id=since_id)

    # 5. Post OTP
    otp_resp = session.post(
        f"{base_url}/oauth/login",
        params={"rid": rid},
        data={"otp": otp},
        allow_redirects=False,
        timeout=10,
    )
    if otp_resp.status_code != 302:
        raise OAuthLoginError(f"OTP verification failed ({otp_resp.status_code})")

    # 6. Consent Allow
    consent_resp = session.post(
        f"{base_url}/oauth/consent",
        params={"rid": rid},
        data={"decision": "allow"},
        allow_redirects=False,
        timeout=10,
    )
    if consent_resp.status_code != 302 or "Location" not in consent_resp.headers:
        raise OAuthLoginError(f"Consent allow failed ({consent_resp.status_code}): {consent_resp.text}")

    cb_url = consent_resp.headers["Location"]
    code = parse_qs(urlparse(cb_url).query)["code"][0]

    # 7. Exchange Code for Access & Refresh Tokens
    token_resp = session.post(
        f"{base_url}/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": "http://localhost/callback",
            "resource": resource_url,
        },
        timeout=10,
    )
    if token_resp.status_code != 200:
        raise OAuthLoginError(f"Token exchange failed ({token_resp.status_code}): {token_resp.text}")

    data = token_resp.json()
    data["client_id"] = client_id
    # Decode claims unverified for test introspection
    data["claims"] = jwt.decode(data["access_token"], options={"verify_signature": False})
    return data


def login_officer_headless(
    username: str,
    password: str,
    resource_url: str,
    base_url: str = "http://localhost:8000",
    client_name: str = "Officer Eval Client"
) -> Dict[str, Any]:
    """Complete block officer headless OAuth flow."""
    session = requests.Session()

    # 1. DCR
    reg_resp = session.post(
        f"{base_url}/oauth/register",
        json={
            "client_name": client_name,
            "redirect_uris": ["http://localhost/callback"],
            "token_endpoint_auth_method": "none",
        },
        timeout=10,
    )
    if reg_resp.status_code != 201:
        raise OAuthLoginError(f"Officer DCR failed ({reg_resp.status_code})")
    client_id = reg_resp.json()["client_id"]

    # 2. Authorize
    verifier, challenge = _generate_pkce()
    auth_resp = session.get(
        f"{base_url}/oauth/authorize",
        params={
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": "http://localhost/callback",
            "scope": "officer",
            "resource": resource_url,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        },
        allow_redirects=False,
        timeout=10,
    )
    if auth_resp.status_code != 302 or "Location" not in auth_resp.headers:
        raise OAuthLoginError(f"Officer authorize failed ({auth_resp.status_code})")

    rid = parse_qs(urlparse(auth_resp.headers["Location"]).query)["rid"][0]

    # 3. Departmental login
    cred_resp = session.post(
        f"{base_url}/oauth/login",
        params={"rid": rid},
        data={"username": username, "password": password},
        allow_redirects=False,
        timeout=10,
    )
    if cred_resp.status_code != 302:
        raise OAuthLoginError(f"Officer credentials rejected ({cred_resp.status_code})")

    # 4. Consent
    consent_resp = session.post(
        f"{base_url}/oauth/consent",
        params={"rid": rid},
        data={"decision": "allow"},
        allow_redirects=False,
        timeout=10,
    )
    if consent_resp.status_code != 302:
        raise OAuthLoginError(f"Officer consent failed ({consent_resp.status_code})")

    code = parse_qs(urlparse(consent_resp.headers["Location"]).query)["code"][0]

    # 5. Token exchange
    token_resp = session.post(
        f"{base_url}/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": "http://localhost/callback",
            "resource": resource_url,
        },
        timeout=10,
    )
    if token_resp.status_code != 200:
        raise OAuthLoginError(f"Officer token exchange failed ({token_resp.status_code}): {token_resp.text}")

    data = token_resp.json()
    data["client_id"] = client_id
    data["claims"] = jwt.decode(data["access_token"], options={"verify_signature": False})
    return data
