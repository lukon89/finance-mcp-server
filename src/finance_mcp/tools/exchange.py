from datetime import UTC, datetime

import httpx
import structlog
from mcp.types import TextContent, Tool

from finance_mcp.config import settings
from finance_mcp.tools import ToolRegistration

log = structlog.get_logger()

# ── In-memory cache: key → (data, fetched_at) ────────────────────────────────
_cache: dict[str, tuple[dict, datetime]] = {}
_MAX_CACHE_SIZE = 256

# ── Tool schemas ──────────────────────────────────────────────────────────────

EXCHANGE_RATE_TOOL = Tool(
    name="get_exchange_rate",
    description="Get current or historical exchange rates. Results cached for 1 hour.",
    inputSchema={
        "type": "object",
        "properties": {
            "base":    {"type": "string", "description": "Base currency (PLN, USD, EUR…)", "default": "PLN"},
            "targets": {"type": "array", "items": {"type": "string"}, "description": "Target currencies", "default": ["USD", "EUR", "GBP", "CHF"]},
            "date":    {"type": "string", "description": "YYYY-MM-DD for historical, omit for latest", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        },
        "required": ["base"],
    },
)

CONVERT_TOOL = Tool(
    name="convert_amount",
    description="Convert a monetary amount from one currency to another using live rates.",
    inputSchema={
        "type": "object",
        "properties": {
            "amount":        {"type": "number",  "description": "Amount to convert"},
            "from_currency": {"type": "string",  "description": "Source currency code"},
            "to_currency":   {"type": "string",  "description": "Target currency code"},
        },
        "required": ["amount", "from_currency", "to_currency"],
    },
)

# ── Implementation ────────────────────────────────────────────────────────────

async def _fetch_rates(base: str, targets: list[str], date: str | None) -> dict:
    """Fetch rates from frankfurter.app with TTL cache."""
    key = f"{base}:{','.join(sorted(targets))}:{date or 'latest'}"
    now = datetime.now(UTC)

    if key in _cache:
        data, fetched = _cache[key]
        if (now - fetched).total_seconds() < settings.exchange_rate_cache_ttl:
            return data

    url = f"{settings.frankfurter_base_url}/{date or 'latest'}"
    log.info("exchange_rate_fetch", base=base, targets=targets, date=date)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, params={"from": base, "to": ",".join(targets)})
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        log.error("exchange_rate_fetch_failed", base=base, targets=targets, error=str(exc))
        raise

    if len(_cache) >= _MAX_CACHE_SIZE:
        oldest = min(_cache, key=lambda k: _cache[k][1])
        del _cache[oldest]

    _cache[key] = (data, now)
    return data


async def handle_get_exchange_rate(args: dict) -> list[TextContent]:
    base    = args["base"].upper()
    targets = [t.upper() for t in args.get("targets", ["USD", "EUR", "GBP", "CHF"])]
    date    = args.get("date")

    data = await _fetch_rates(base, targets, date)
    rows = "\n".join(f"| {k} | {v:.6f} | {1/v:.6f} |" for k, v in data["rates"].items())
    text = (
        f"Exchange rates — **{data['base']}** on {data['date']}\n\n"
        f"| Currency | Rate | Inverse |\n|---|---|---|\n{rows}"
    )
    return [TextContent(type="text", text=text)]


async def handle_convert_amount(args: dict) -> list[TextContent]:
    amount   = float(args["amount"])
    from_cur = args["from_currency"].upper()
    to_cur   = args["to_currency"].upper()

    data = await _fetch_rates(from_cur, [to_cur], None)
    rate      = data["rates"][to_cur]
    converted = amount * rate

    text = (
        f"{amount:,.2f} **{from_cur}** = **{converted:,.2f} {to_cur}**\n"
        f"Rate: {rate:.6f} ({data['date']})"
    )
    return [TextContent(type="text", text=text)]


# ── Registration ──────────────────────────────────────────────────────────────

TOOLS: list[ToolRegistration] = [
    (EXCHANGE_RATE_TOOL, handle_get_exchange_rate),
    (CONVERT_TOOL, handle_convert_amount),
]
