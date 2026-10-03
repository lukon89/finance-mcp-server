import asyncio

import structlog
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    GetPromptResult, Prompt, Resource, TextContent, TextResourceContents, Tool,
)

from finance_mcp.db.setup import init_db
from finance_mcp.prompts.templates import PROMPTS, resolve_prompt
from finance_mcp.resources.reports import get_monthly_report, get_recent_transactions
from finance_mcp.tools import ToolHandler
from finance_mcp.tools import exchange, transactions

log = structlog.get_logger()

mcp = Server("finance-mcp")

# ── Tools ─────────────────────────────────────────────────────────────────────
# Each tool module exports TOOLS: list[ToolRegistration]; adding a new domain
# module only requires listing it here, not touching list_tools/call_tool.

_TOOL_MODULES = [exchange, transactions]

_TOOLS: list[Tool] = []
_HANDLERS: dict[str, ToolHandler] = {}
for _module in _TOOL_MODULES:
    for _tool, _handler in _module.TOOLS:
        _TOOLS.append(_tool)
        _HANDLERS[_tool.name] = _handler


@mcp.list_tools()
async def list_tools() -> list[Tool]:
    return _TOOLS


@mcp.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handler = _HANDLERS.get(name)
    if handler is None:
        log.warning("unknown_tool_requested", tool=name)
        raise ValueError(f"Unknown tool: {name}")

    log.info("tool_called", tool=name, arguments=arguments)
    try:
        return await handler(arguments)
    except Exception:
        log.error("tool_call_failed", tool=name, exc_info=True)
        raise

# ── Resources ─────────────────────────────────────────────────────────────────

@mcp.list_resources()
async def list_resources() -> list[Resource]:
    return [
        Resource(uri="finance://transactions/recent",      name="Recent Transactions (30d)",  mimeType="text/markdown"),
        Resource(uri="finance://reports/monthly/latest",   name="Current Month Report",       mimeType="text/markdown"),
    ]


@mcp.read_resource()
async def read_resource(uri: str) -> list[TextResourceContents]:
    if uri == "finance://transactions/recent":
        text = await get_recent_transactions()
    elif uri.startswith("finance://reports/monthly/"):
        spec = uri.removeprefix("finance://reports/monthly/")
        text = await get_monthly_report(spec)
    else:
        log.warning("unknown_resource_requested", uri=uri)
        raise ValueError(f"Unknown resource URI: {uri}")
    return [TextResourceContents(uri=uri, mimeType="text/markdown", text=text)]

# ── Prompts ───────────────────────────────────────────────────────────────────

@mcp.list_prompts()
async def list_prompts() -> list[Prompt]:
    return PROMPTS


@mcp.get_prompt()
async def get_prompt(name: str, arguments: dict | None) -> GetPromptResult:
    return await resolve_prompt(name, arguments or {})

# ── Entry point ───────────────────────────────────────────────────────────────

async def _run() -> None:
    await init_db()
    log.info("stdio_server_started", tools=len(_TOOLS))
    async with stdio_server() as (read_stream, write_stream):
        await mcp.run(read_stream, write_stream, mcp.create_initialization_options())


def main() -> None:
    asyncio.run(_run())
