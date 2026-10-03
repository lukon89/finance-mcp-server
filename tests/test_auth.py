import time

import httpx
import pytest
from jose import JWTError

from finance_mcp.auth.oauth import create_jwt, verify_jwt
from finance_mcp.auth.middleware import _check_rate_limit, _windows
from finance_mcp.config import settings


# ── JWT tests ─────────────────────────────────────────────────────────────────

def test_create_and_verify_roundtrip():
    user = {"sub": "g-12345", "email": "test@example.com", "name": "Test User"}
    token = create_jwt(user)
    payload = verify_jwt(token)
    assert payload["email"] == "test@example.com"
    assert payload["sub"] == "g-12345"


def test_invalid_jwt_raises():
    with pytest.raises(JWTError):
        verify_jwt("not.a.real.token")


def test_tampered_signature_raises():
    token = create_jwt({"sub": "x", "email": "x@x.com", "name": "X"})
    header, body, _ = token.split(".")
    with pytest.raises(JWTError):
        verify_jwt(f"{header}.{body}.invalidsig")


# ── Rate limiter tests ────────────────────────────────────────────────────────

def test_rate_limit_allows_up_to_limit(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_minute", 3)
    _windows.clear()
    user_id = "test-rate-user"
    for _ in range(3):
        _check_rate_limit(user_id)  # should not raise


def test_rate_limit_blocks_over_limit(monkeypatch):
    from fastapi import HTTPException
    monkeypatch.setattr(settings, "rate_limit_per_minute", 2)
    _windows.clear()
    user_id = "test-rate-block"
    _check_rate_limit(user_id)
    _check_rate_limit(user_id)
    with pytest.raises(HTTPException) as exc_info:
        _check_rate_limit(user_id)
    assert exc_info.value.status_code == 429


# ── HTTP route tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_is_public():
    from finance_mcp.http_server import http_app
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=http_app), base_url="http://test"
    ) as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_sse_requires_bearer_token():
    from finance_mcp.http_server import http_app
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=http_app), base_url="http://test"
    ) as client:
        resp = await client.get("/sse")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sse_rejects_invalid_token():
    from finance_mcp.http_server import http_app
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=http_app), base_url="http://test"
    ) as client:
        resp = await client.get("/sse", headers={"Authorization": "Bearer garbage.token.here"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_messages_requires_auth():
    from finance_mcp.http_server import http_app
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=http_app), base_url="http://test"
    ) as client:
        resp = await client.post("/messages", content=b"{}")
    assert resp.status_code == 401
