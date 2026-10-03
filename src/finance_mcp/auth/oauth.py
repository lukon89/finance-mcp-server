import hashlib
import base64
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import structlog
from jose import jwt, JWTError

from finance_mcp.config import settings

log = structlog.get_logger()

# ── Google endpoints ──────────────────────────────────────────────────────────
_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_INFO_URL  = "https://www.googleapis.com/oauth2/v3/userinfo"

# In-memory PKCE store: state → (code_verifier, created_at)
# Entries expire after _PKCE_TTL_SECONDS; eviction runs on each build_auth_url call.
# In production: replace with Redis or a DB table with native TTL.
_PKCE_TTL_SECONDS = 600  # 10 minutes
_pending: dict[str, tuple[str, float]] = {}


# ── PKCE helpers ──────────────────────────────────────────────────────────────

def _pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for PKCE S256."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    digest    = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


# ── Public API ────────────────────────────────────────────────────────────────

def build_auth_url() -> str:
    """Generate a Google OAuth authorization URL and stash the PKCE verifier."""
    now = time.monotonic()

    # Evict entries older than TTL so _pending doesn't grow unboundedly
    expired = [k for k, (_, ts) in _pending.items() if now - ts > _PKCE_TTL_SECONDS]
    for k in expired:
        del _pending[k]

    state = secrets.token_urlsafe(16)
    verifier, challenge = _pkce_pair()
    _pending[state] = (verifier, now)

    params = {
        "client_id":             settings.oauth_client_id,
        "redirect_uri":          settings.oauth_redirect_uri,
        "response_type":         "code",
        "scope":                 "openid email profile",
        "state":                 state,
        "code_challenge":        challenge,
        "code_challenge_method": "S256",
        "access_type":           "online",
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str, state: str) -> dict:
    """
    Exchange an authorization code for Google user info.
    Pops the stored verifier — replaying the same state raises ValueError.
    """
    entry = _pending.pop(state, None)
    if entry is None:
        log.warning("oauth_invalid_state", state=state)
        raise ValueError("Invalid or expired OAuth state")

    verifier, _ = entry

    async with httpx.AsyncClient() as client:
        try:
            token_resp = await client.post(_TOKEN_URL, data={
                "client_id":     settings.oauth_client_id,
                "client_secret": settings.oauth_client_secret,
                "code":          code,
                "redirect_uri":  settings.oauth_redirect_uri,
                "grant_type":    "authorization_code",
                "code_verifier": verifier,
            })
            token_resp.raise_for_status()
            access_token = token_resp.json()["access_token"]

            info_resp = await client.get(
                _INFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            info_resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            log.error("oauth_google_request_failed", url=str(exc.request.url), status=exc.response.status_code)
            raise

        return info_resp.json()   # {sub, email, name, picture}


def create_jwt(user_info: dict) -> str:
    """Issue a signed JWT for an authenticated user."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub":   user_info["sub"],
        "email": user_info["email"],
        "name":  user_info.get("name", ""),
        "iat":   now,
        "exp":   now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_jwt(token: str) -> dict:
    """Decode and verify a JWT. Raises jose.JWTError on any failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
