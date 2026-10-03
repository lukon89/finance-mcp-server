import pytest

from finance_mcp.prompts.templates import (
    analyze_spending,
    budget_review,
    currency_exposure,
)
from finance_mcp.resources.reports import get_monthly_report, get_recent_transactions

# ── Resource tests ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_recent_transactions_returns_table():
    result = await get_recent_transactions()
    # Seed covers last 6 months, so last 30 days always has rows
    assert "# Recent Transactions" in result
    assert "No transactions" not in result
    assert "| Date |" in result


@pytest.mark.asyncio
async def test_get_recent_transactions_respects_limit():
    result = await get_recent_transactions(limit=2)
    assert "# Recent Transactions" in result
    data_rows = [line for line in result.splitlines() if line.startswith("| 20")]
    assert len(data_rows) <= 2


@pytest.mark.asyncio
async def test_get_monthly_report_latest():
    result = await get_monthly_report("latest")
    # Seed includes transactions for today's month
    assert "# Monthly Report" in result
    assert "## By Category" in result
    assert "## Top 5 Expenses" in result


@pytest.mark.asyncio
async def test_get_monthly_report_no_data():
    result = await get_monthly_report("1900-01")
    assert "No data for 1900-01" in result


# ── Prompt tests ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_analyze_spending_prompt_contains_period():
    result = await analyze_spending(period="last month")
    assert "last month" in result


@pytest.mark.asyncio
async def test_analyze_spending_prompt_with_focus():
    result = await analyze_spending(period="Q3 2026", focus="Food")
    assert "Q3 2026" in result
    assert "Food" in result


@pytest.mark.asyncio
async def test_budget_review_prompt_contains_budget():
    result = await budget_review(budget_pln="5000")
    assert "5000" in result


@pytest.mark.asyncio
async def test_currency_exposure_prompt_renders():
    result = await currency_exposure()
    assert "currency" in result.lower()
    assert len(result) > 50
