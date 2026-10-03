from datetime import UTC, datetime

import httpx
import structlog

from finance_mcp.config import settings

log = structlog.get_logger()

# ── In-memory cache: key → (data, fetched_at) ────────────────────────────────
_cache: dict[str, tuple[dict, datetime]] = {}
_MAX_CACHE_SIZE = 256


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


async def get_exchange_rate(
    base:    str = "PLN",
    targets: list[str] = ["USD", "EUR", "GBP", "CHF"],  # noqa: B006
    date:    str | None = None,
) -> str:
    """Get current or historical exchange rates. Results cached for 1 hour."""
    base    = base.upper()
    targets = [t.upper() for t in targets]
    data    = await _fetch_rates(base, targets, date)
    rows    = "\n".join(f"| {k} | {v:.6f} | {1/v:.6f} |" for k, v in data["rates"].items())
    return (
        f"Exchange rates — **{data['base']}** on {data['date']}\n\n"
        f"| Currency | Rate | Inverse |\n|---|---|---|\n{rows}"
    )


async def convert_amount(
    amount:        float,
    from_currency: str,
    to_currency:   str,
) -> str:
    """Convert a monetary amount from one currency to another using live rates."""
    from_cur  = from_currency.upper()
    to_cur    = to_currency.upper()
    data      = await _fetch_rates(from_cur, [to_cur], None)
    rate      = data["rates"][to_cur]
    converted = amount * rate
    return (
        f"{amount:,.2f} **{from_cur}** = **{converted:,.2f} {to_cur}**\n"
        f"Rate: {rate:.6f} ({data['date']})"
    )
