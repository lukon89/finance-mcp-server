import httpx
import pytest
import respx

from finance_mcp.tools.exchange import convert_amount, get_exchange_rate
from finance_mcp.tools.transactions import search_transactions, spending_summary

FRANKFURTER_BASE = "https://api.frankfurter.app"

# ── Exchange rate tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_get_exchange_rate_returns_markdown_table():
    respx.get(f"{FRANKFURTER_BASE}/latest").mock(return_value=httpx.Response(200, json={
        "base": "PLN", "date": "2026-10-01", "rates": {"USD": 0.2525, "EUR": 0.2315},
    }))
    result = await get_exchange_rate(base="PLN", targets=["USD", "EUR"])
    assert "USD" in result
    assert "0.252500" in result


@pytest.mark.asyncio
@respx.mock
async def test_convert_amount_calculates_correctly():
    respx.get(f"{FRANKFURTER_BASE}/latest").mock(return_value=httpx.Response(200, json={
        "base": "PLN", "date": "2026-10-01", "rates": {"USD": 0.25},
    }))
    result = await convert_amount(amount=1000, from_currency="PLN", to_currency="USD")
    assert "250.00 USD" in result


@pytest.mark.asyncio
@respx.mock
async def test_exchange_rate_api_error_propagates():
    respx.get(f"{FRANKFURTER_BASE}/latest").mock(return_value=httpx.Response(503))
    with pytest.raises(httpx.HTTPStatusError):
        await get_exchange_rate(base="PLN", targets=["USD"])


# ── Transaction tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_transactions_no_match():
    result = await search_transactions(query="NONEXISTENT_XYZ_ZZZZ")
    assert "No transactions found" in result


@pytest.mark.asyncio
async def test_search_transactions_by_category():
    result = await search_transactions(category="Food", limit=5)
    # Seed data (random.seed=42) guarantees Food rows in the last 6 months
    assert "Food" in result
    assert "No transactions" not in result


@pytest.mark.asyncio
async def test_spending_summary_returns_table():
    result = await spending_summary(period="last_30_days", group_by="category")
    assert "Spending" in result


@pytest.mark.asyncio
async def test_spending_summary_income_excluded_by_default():
    result = await spending_summary(period="last_30_days", include_income=False)
    if "No data" not in result:
        import re
        totals = re.findall(r"\| ([+-][\d.]+) \|", result)
        for t in totals:
            assert float(t) <= 0, f"Expected expense (negative), got {t}"
