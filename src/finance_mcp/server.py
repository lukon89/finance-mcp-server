import asyncio

import structlog
from mcp.server.mcpserver import MCPServer

from finance_mcp.db.setup import init_db
from finance_mcp.prompts.templates import (
    analyze_spending,
    budget_review,
    currency_exposure,
)
from finance_mcp.resources.reports import get_monthly_report, get_recent_transactions
from finance_mcp.tools.exchange import convert_amount, get_exchange_rate
from finance_mcp.tools.transactions import search_transactions, spending_summary

log = structlog.get_logger()

mcp = MCPServer("finance-mcp")

# ── Tools ─────────────────────────────────────────────────────────────────────

mcp.tool()(search_transactions)
mcp.tool()(spending_summary)
mcp.tool()(get_exchange_rate)
mcp.tool()(convert_amount)

# ── Resources ─────────────────────────────────────────────────────────────────

@mcp.resource("finance://transactions/recent", name="Recent Transactions (30d)", mime_type="text/markdown")
async def recent_transactions_resource() -> str:
    return await get_recent_transactions()


@mcp.resource("finance://reports/monthly/{month_spec}", name="Monthly Report", mime_type="text/markdown")
async def monthly_report_resource(month_spec: str) -> str:
    return await get_monthly_report(month_spec)

# ── Prompts ───────────────────────────────────────────────────────────────────

mcp.prompt()(analyze_spending)
mcp.prompt()(budget_review)
mcp.prompt()(currency_exposure)

# ── Entry point ───────────────────────────────────────────────────────────────

async def _run() -> None:
    await init_db()
    log.info("stdio_server_started")
    await mcp.run_stdio_async()


def main() -> None:
    asyncio.run(_run())
