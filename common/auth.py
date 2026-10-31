# -*- coding: utf-8 -*-
"""
Sewa Setu - Common Authentication & Token Verification (RFC 8707, RFC 9728)
Verifies RS256 JWT tokens issued by the Sewa Setu portal against its JWKS.
Enforces audience restrictions, scope checks, and live session grant validity.
"""

import os
import time
import logging
from typing import Optional, Dict, Any, Tuple
import jwt
import requests

logger = logging.getLogger("mcp.auth")

PORTAL_INTERNAL_URL = os.environ.get("PORTAL_INTERNAL_URL", "http://localhost:8000").rstrip("/")
ISSUER = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "dev-internal-key-2026")

_JWKS_CACHE: Dict[str, Any] = {}
_JWKS_LAST_FETCH: float = 0.0
JWKS_CACHE_TTL = 300.0  # 5 minutes


class AuthError(Exception):
    def __init__(self, status_code: int, error: str, message: str, www_authenticate: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.error = error
        self.message = message
        self.www_authenticate = www_authenticate


def _fetch_jwks(force: bool = False) -> None:
    global _JWKS_CACHE, _JWKS_LAST_FETCH
    now = time.time()
    if not force and _JWKS_CACHE and (now - _JWKS_LAST_FETCH < JWKS_CACHE_TTL):
        return

    jwks_url = f"{PORTAL_INTERNAL_URL}/.well-known/jwks.json"
    try:
        resp = requests.get(jwks_url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        new_cache = {}
        for key_dict in data.get("keys", []):
            kid = key_dict.get("kid")
            if kid:
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_dict)
                new_cache[kid] = public_key
        _JWKS_CACHE = new_cache
        _JWKS_LAST_FETCH = now
        logger.info("Fetched %d public key(s) from portal JWKS", len(_JWKS_CACHE))
    except Exception as e:
        logger.error("Failed to fetch JWKS from %s: %s", jwks_url, e)
        if not _JWKS_CACHE:
            raise AuthError(500, "jwks_unavailable", "Could not retrieve authorization server keys")


def verify_bearer_token(
    raw_token: str,
    expected_scope: Optional[str] = None,
    expected_audience: Optional[str] = None,
    resource_metadata_url: Optional[str] = None
) -> Dict[str, Any]:
    """Verify an RS256 Bearer JWT against Sewa Setu portal JWKS.

    Validates:
      1. RS256 signature against published JWKS
      2. Expiration (exp)
      3. Issuer (iss == ISSUER)
      4. Audience (aud == expected_audience, with/without trailing slash)
      5. Scope (expected_scope in scope, if specified)
      6. Active session grant check via internal portal API (/internal/v1/session_check)
    """
    www_auth_header = f'Bearer realm="{ISSUER}"'
    if expected_audience:
        www_auth_header += f', resource="{expected_audience}"'
    if resource_metadata_url:
        www_auth_header += f', resource_metadata="{resource_metadata_url}"'

    if not raw_token or not raw_token.strip():
        raise AuthError(
            401,
            "missing_token",
            "Authentication required. Please sign in via OAuth.",
            www_authenticate=www_auth_header
        )

    # Decode header to read kid
    try:
        unverified_headers = jwt.get_unverified_header(raw_token)
        kid = unverified_headers.get("kid")
    except Exception:
        raise AuthError(401, "invalid_token", "Malformed JWT header", www_authenticate=www_auth_header)

    _fetch_jwks()
    if kid not in _JWKS_CACHE:
        # Retry once on unknown kid
        _fetch_jwks(force=True)
        if kid not in _JWKS_CACHE:
            raise AuthError(401, "invalid_token", f"Unknown signing key ID '{kid}'", www_authenticate=www_auth_header)

    public_key = _JWKS_CACHE[kid]

    # Verify signature and expiration
    try:
        claims = jwt.decode(
            raw_token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False, "verify_iss": False, "verify_exp": True}
        )
    except jwt.ExpiredSignatureError:
        raise AuthError(401, "token_expired", "Access token has expired. Please refresh your session.", www_authenticate=www_auth_header)
    except jwt.InvalidTokenError as e:
        raise AuthError(401, "invalid_token", f"Token cryptographic verification failed: {e}", www_authenticate=www_auth_header)

    # 1. Issuer check (RFC 9207)
    claim_iss = (claims.get("iss") or "").rstrip("/")
    if claim_iss != ISSUER:
        logger.warning("Issuer mismatch: expected %s, got %s", ISSUER, claim_iss)
        raise AuthError(401, "invalid_issuer", f"Token issuer mismatch. Expected {ISSUER}.", www_authenticate=www_auth_header)

    # 2. Strict RFC 8707 audience check
    if expected_audience:
        claim_aud = (claims.get("aud") or "").rstrip("/")
        canonical_expected_aud = expected_audience.rstrip("/")
        if claim_aud != canonical_expected_aud:
            logger.warning("Audience mismatch: expected %s, got %s", canonical_expected_aud, claim_aud)
            if claim_aud == ISSUER:
                desc = "Token was issued for the portal root rather than this specific service. Please include resource indicator in your authorization request."
            else:
                desc = f"Token audience '{claim_aud}' does not match this server's resource URL '{canonical_expected_aud}'."
            raise AuthError(401, "invalid_target", desc, www_authenticate=www_auth_header)

    # 3. Scope validation
    if expected_scope:
        token_scopes = (claims.get("scope") or "").split()
        if expected_scope not in token_scopes:
            logger.warning("Scope mismatch: required %s, token has %s", expected_scope, token_scopes)
            if expected_scope == "officer":
                msg = "This sign-in is for citizen services. An officer sign-in is required to access officer tools."
            else:
                msg = "This sign-in is for officer services. A citizen sign-in is required to access citizen tools."
            raise AuthError(403, "insufficient_scope", msg)

    # 4. Live Session Check against Portal
    # Tokens remain valid only while an active unrevoked grant exists in the portal
    sub = claims.get("sub", "")
    client_id = claims.get("client_id", "")
    jti = claims.get("jti", "") if claims.get("kind") == "program" else ""

    session_chk_url = f"{PORTAL_INTERNAL_URL}/internal/v1/session_check"
    try:
        chk_resp = requests.get(
            session_chk_url,
            headers={"X-Internal-Service-Key": INTERNAL_API_KEY},
            params={"sub": sub, "client_id": client_id, "jti": jti},
            timeout=5
        )
        if chk_resp.status_code == 200:
            chk_data = chk_resp.json()
            if not chk_data.get("valid"):
                reason = chk_data.get("reason", "Session revoked or expired")
                logger.info("Session check failed for sub=%s: %s", sub, reason)
                raise AuthError(401, "session_revoked", f"Sign-in session ended: {reason}. Please sign in again.", www_authenticate=www_auth_header)
        else:
            logger.warning("Session check endpoint returned %d", chk_resp.status_code)
    except AuthError:
        raise
    except Exception as e:
        logger.error("Session check network error: %s", e)

    return claims


def get_protected_resource_metadata(server_canonical_url: str, server_scope: str) -> Dict[str, Any]:
    """RFC 9728: OAuth 2.0 Protected Resource Metadata document."""
    return {
        "resource": server_canonical_url,
        "authorization_servers": [ISSUER],
        "scopes_supported": [server_scope],
        "bearer_methods_supported": ["header"],
        "resource_documentation": f"{ISSUER}/about",
    }


class SewaSetuTokenVerifier:
    """TokenVerifier implementation for Sewa Setu MCP servers."""

    def __init__(self, resource_server_url: str):
        self.resource_server_url = resource_server_url

    async def verify_token(self, token: str) -> Optional[Any]:
        from mcp.server.auth.provider import AccessToken
        try:
            claims = verify_bearer_token(
                raw_token=token,
                expected_scope=None,  # Handled by RequireAuthMiddleware for proper 403 response
                expected_audience=self.resource_server_url,
                resource_metadata_url=f"{self.resource_server_url}/.well-known/oauth-protected-resource"
            )
            scopes_str = claims.get("scope") or ""
            scopes_list = scopes_str.split() if isinstance(scopes_str, str) else list(scopes_str)
            return AccessToken(
                token=token,
                client_id=claims.get("client_id", ""),
                scopes=scopes_list,
                expires_at=claims.get("exp"),
                resource=claims.get("aud"),
                subject=claims.get("sub"),
                claims=claims
            )
        except AuthError as e:
            logger.warning("Token verification failed: %s (%s)", e.error, e.message)
            return None


def get_subject_from_context() -> Tuple[str, str]:
    """Retrieve verified subject (role, identifier) from the current request context.

    Returns:
        (role, identifier), e.g. ("citizen", "9876543210") or ("officer", "anjali")
    Raises:
        AuthError: If no valid authentication exists in the current context.
    """
    from mcp.server.auth.middleware.auth_context import get_access_token
    token = get_access_token()
    if not token or not token.subject:
        raise AuthError(401, "missing_token", "No authenticated subject found in request context")

    parts = token.subject.split(":", 1)
    if len(parts) != 2:
        raise AuthError(401, "invalid_subject", f"Malformed subject claim '{token.subject}'")

    return parts[0], parts[1]
