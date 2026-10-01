import json

import structlog
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from mcp.server.sse import SseServerTransport

from finance_mcp.auth.middleware import require_auth
from finance_mcp.auth.oauth import build_auth_url, create_jwt, exchange_code
from finance_mcp.config import settings
from finance_mcp.db.setup import init_db
from finance_mcp.server import mcp  # reuse the same Server instance

log = structlog.get_logger()

http_app = FastAPI(title="Finance MCP Server", version="0.1.0", docs_url="/docs")
sse      = SseServerTransport("/messages")

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

    return HTMLResponse(f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>Finance MCP — Authenticated</title>
<style>
  body {{ font-family: monospace; background: #0f1117; color: #e2e8f0; padding: 2rem; }}
  h2 {{ color: #64ffda; }} p {{ color: #8892b0; }}
  pre {{ background: #1a1d27; border: 1px solid #2e3250; border-radius: 8px;
         padding: 1.2rem; overflow: auto; font-size: 0.85rem; color: #f1fa8c; }}
  a {{ color: #64ffda; }}
</style></head><body>
<h2>✅ Authenticated as {user_info['email']}</h2>
<p>Add to <code>~/.claude/claude_desktop_config.json</code> (token expires in {settings.jwt_expire_minutes} min):</p>
<pre>{config_snippet}</pre>
<p><a href="/auth/login">Renew token</a> · <a href="/docs">API docs</a> · <a href="/health">Health</a></p>
</body></html>""")


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
        await mcp.run(streams[0], streams[1], mcp.create_initialization_options())


@http_app.post("/messages")
async def messages_endpoint(request: Request, user: dict = Depends(require_auth)):
    """Client posts MCP messages here (paired with /sse GET)."""
    await sse.handle_post_message(request.scope, request.receive, request._send)


# ── Startup ───────────────────────────────────────────────────────────────────

@http_app.on_event("startup")
async def on_startup():
    await init_db()
    log.info("http_server_started", host=settings.host, port=settings.port)


def main() -> None:
    uvicorn.run(http_app, host=settings.host, port=settings.port, log_level="info")
