import json
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, FileSystemLoader, select_autoescape
from mcp.server.sse import SseServerTransport

from finance_mcp.auth.middleware import require_auth
from finance_mcp.auth.oauth import build_auth_url, create_jwt, exchange_code
from finance_mcp.config import settings
from finance_mcp.db.setup import init_db
from finance_mcp.server import mcp  # reuse the same Server instance

log = structlog.get_logger()

TEMPLATES_DIR = Path(__file__).parent / "templates"
_jinja = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
)

sse = SseServerTransport("/messages")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.jwt_secret == "dev-secret-change-in-production":
        log.warning("jwt_default_secret_in_use", hint="Set JWT_SECRET env var before deploying to production")
    await init_db()
    log.info("http_server_started", host=settings.host, port=settings.port)
    yield


http_app = FastAPI(title="Finance MCP Server", version="0.1.0", docs_url="/docs", lifespan=lifespan)

# ── Auth routes ───────────────────────────────────────────────────────────────

@http_app.get("/auth/login", include_in_schema=False)
async def login():
    """Redirect user to Google OAuth consent screen."""
    return RedirectResponse(build_auth_url())


@http_app.get("/auth/callback", include_in_schema=False)
async def callback(code: str, state: str):
    """Handle Google redirect, issue JWT, show it to the user."""
    try:
        user_info = await exchange_code(code, state)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    token = create_jwt(user_info)
    log.info("user_authenticated", email=user_info["email"])

    config_snippet = json.dumps({
        "mcpServers": {
            "finance": {
                "url": f"http://{settings.host}:{settings.port}/sse",
                "headers": {"Authorization": f"Bearer {token}"},
            }
        }
    }, indent=2)

    html = _jinja.get_template("callback.html").render(
        email=user_info["email"],
        expire_minutes=settings.jwt_expire_minutes,
        config_snippet=config_snippet,
    )
    return HTMLResponse(html)


# ── Health ────────────────────────────────────────────────────────────────────

@http_app.get("/health")
async def health():
    return {"status": "ok", "server": "finance-mcp", "version": "0.1.0"}


# ── MCP over SSE (protected) ──────────────────────────────────────────────────

@http_app.get("/sse")
async def sse_endpoint(request: Request, user: dict = Depends(require_auth)):
    """SSE endpoint — Claude connects here and streams JSON-RPC messages."""
    log.info("sse_connected", email=user.get("email"))
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await mcp._lowlevel_server.run(streams[0], streams[1], mcp._lowlevel_server.create_initialization_options())


@http_app.post("/messages")
async def messages_endpoint(request: Request, user: dict = Depends(require_auth)):
    """Client posts MCP messages here (paired with /sse GET)."""
    await sse.handle_post_message(request.scope, request.receive, request._send)


def main() -> None:
    uvicorn.run(http_app, host=settings.host, port=settings.port, log_level="info")
