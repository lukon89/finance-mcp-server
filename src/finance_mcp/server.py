import asyncio

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    GetPromptResult, Prompt, Resource, TextContent, TextResourceContents, Tool,
)

from finance_mcp.db.setup import init_db
from finance_mcp.prompts.templates import PROMPTS, resolve_prompt
from finance_mcp.resources.reports import get_monthly_report, get_recent_transactions
from finance_mcp.tools.exchange import (
    CONVERT_TOOL, EXCHANGE_RATE_TOOL,
    handle_convert_amount, handle_get_exchange_rate,
)
from finance_mcp.tools.transactions import (
    SEARCH_TOOL, SUMMARY_TOOL,
    handle_search_transactions, handle_spending_summary,
)

mcp = Server("finance-mcp")

# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.list_tools()
async def list_tools() -> list[Tool]:
    return [EXCHANGE_RATE_TOOL, CONVERT_TOOL, SEARCH_TOOL, SUMMARY_TOOL]


@mcp.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    match name:
        case "get_exchange_rate":    return await handle_get_exchange_rate(arguments)
        case "convert_amount":       return await handle_convert_amount(arguments)
        case "search_transactions":  return await handle_search_transactions(arguments)
        case "get_spending_summary": return await handle_spending_summary(arguments)
        case _: raise ValueError(f"Unknown tool: {name}")

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
    async with stdio_server() as (read_stream, write_stream):
        await mcp.run(read_stream, write_stream, mcp.create_initialization_options())


def main() -> None:
    asyncio.run(_run())
