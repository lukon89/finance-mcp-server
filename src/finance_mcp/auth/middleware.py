from collections import defaultdict
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from jose import JWTError

from finance_mcp.auth.oauth import verify_jwt
from finance_mcp.config import settings

# Sliding-window rate limiter: user_id → list of request timestamps
_windows: dict[str, list[float]] = defaultdict(list)
_WINDOW_SECONDS = 60.0


def _check_rate_limit(user_id: str) -> None:
    now = datetime.now(timezone.utc).timestamp()
    hits = _windows[user_id]
    # Drop timestamps outside the current window
    _windows[user_id] = [t for t in hits if now - t < _WINDOW_SECONDS]
    if len(_windows[user_id]) >= settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({settings.rate_limit_per_minute} req/min)",
            headers={"Retry-After": "60"},
        )
    _windows[user_id].append(now)


async def require_auth(request: Request) -> dict:
    """
    FastAPI dependency used on protected routes.

    Validates the Bearer JWT in the Authorization header,
    enforces per-user rate limiting, and returns the token payload.
    Raises HTTP 401 for missing/invalid tokens, 429 for rate limit.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")

    token = auth.removeprefix("Bearer ").strip()
    try:
        payload = verify_jwt(token)
    except JWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")

    _check_rate_limit(payload["sub"])
    return payload
