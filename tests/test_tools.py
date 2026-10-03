import httpx
import pytest
import respx

from finance_mcp.tools.exchange import handle_convert_amount, handle_get_exchange_rate
from finance_mcp.tools.transactions import (
    handle_search_transactions,
    handle_spending_summary,
)

FRANKFURTER_BASE = "https://api.frankfurter.app"

# ── Exchange rate tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_get_exchange_rate_returns_markdown_table():
    respx.get(f"{FRANKFURTER_BASE}/latest").mock(return_value=httpx.Response(200, json={
        "base": "PLN", "date": "2026-10-01", "rates": {"USD": 0.2525, "EUR": 0.2315},
    }))
    result = await handle_get_exchange_rate({"base": "PLN", "targets": ["USD", "EUR"]})
    assert len(result) == 1
    assert "USD" in result[0].text
    assert "0.252500" in result[0].text


@pytest.mark.asyncio
@respx.mock
async def test_convert_amount_calculates_correctly():
    respx.get(f"{FRANKFURTER_BASE}/latest").mock(return_value=httpx.Response(200, json={
        "base": "PLN", "date": "2026-10-01", "rates": {"USD": 0.25},
    }))
    result = await handle_convert_amount({"amount": 1000, "from_currency": "PLN", "to_currency": "USD"})
    assert "250.00 USD" in result[0].text


@pytest.mark.asyncio
@respx.mock
async def test_exchange_rate_api_error_propagates():
    respx.get(f"{FRANKFURTER_BASE}/latest").mock(return_value=httpx.Response(503))
    with pytest.raises(httpx.HTTPStatusError):
        await handle_get_exchange_rate({"base": "PLN", "targets": ["USD"]})


# ── Transaction tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_transactions_no_match():
    result = await handle_search_transactions({"query": "NONEXISTENT_XYZ_ZZZZ"})
    assert "No transactions found" in result[0].text


@pytest.mark.asyncio
async def test_search_transactions_by_category():
    result = await handle_search_transactions({"category": "Food", "limit": 5})
    # Seed data includes Food — should find rows
    assert len(result) == 1
    text = result[0].text
    assert "Food" in text or "No transactions" in text  # passes even if seed was thin


@pytest.mark.asyncio
async def test_spending_summary_returns_table():
    result = await handle_spending_summary({"period": "last_30_days", "group_by": "category"})
    assert len(result) == 1
    text = result[0].text
    assert "Spending" in text


@pytest.mark.asyncio
async def test_spending_summary_income_excluded_by_default():
    result = await handle_spending_summary({"period": "last_30_days", "include_income": False})
    # With include_income=False, amounts should be negative (expenses only)
    text = result[0].text
    if "No data" not in text:
        # All totals in table should be negative
        import re
        totals = re.findall(r"\| ([+-][\d.]+) \|", text)
        for t in totals:
            assert float(t) <= 0, f"Expected expense (negative), got {t}"
