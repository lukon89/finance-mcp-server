from datetime import UTC, datetime

import structlog
from fastapi import HTTPException, Request
from jose import JWTError

from finance_mcp.auth.oauth import verify_jwt
from finance_mcp.config import settings

log = structlog.get_logger()

# Sliding-window rate limiter: user_id → list of request timestamps.
# Plain dict instead of defaultdict so no key is created until a user actually
# makes a request. Keys stay with an empty list once all timestamps expire, but
# that's a trivially small footprint for a dev-scale user set.
_windows: dict[str, list[float]] = {}
_WINDOW_SECONDS = 60.0


def _check_rate_limit(user_id: str) -> None:
    now  = datetime.now(UTC).timestamp()
    hits = [t for t in _windows.get(user_id, []) if now - t < _WINDOW_SECONDS]
    if len(hits) >= settings.rate_limit_per_minute:
        log.warning("rate_limit_exceeded", user_id=user_id, hits=len(hits))
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({settings.rate_limit_per_minute} req/min)",
            headers={"Retry-After": "60"},
        )
    _windows[user_id] = hits + [now]


async def require_auth(request: Request) -> dict:
    """
    FastAPI dependency used on protected routes.

    Validates the Bearer JWT in the Authorization header,
    enforces per-user rate limiting, and returns the token payload.
    Raises HTTP 401 for missing/invalid tokens, 429 for rate limit.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        log.warning("auth_missing_bearer_token", path=request.url.path)
        raise HTTPException(status_code=401, detail="Bearer token required")

    token = auth.removeprefix("Bearer ").strip()
    try:
        payload = verify_jwt(token)
    except JWTError as exc:
        log.warning("auth_invalid_token", path=request.url.path, error=str(exc))
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")

    _check_rate_limit(payload["sub"])
    return payload
