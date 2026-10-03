import pytest

from finance_mcp.prompts.templates import resolve_prompt
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
    result = await resolve_prompt("analyze_spending", {"period": "last month"})
    text = result.messages[0].content.text
    assert "last month" in text
    assert result.description == "Spending analysis — last month"


@pytest.mark.asyncio
async def test_analyze_spending_prompt_with_focus():
    result = await resolve_prompt("analyze_spending", {"period": "Q3 2026", "focus": "Food"})
    text = result.messages[0].content.text
    assert "Q3 2026" in text
    assert "Food" in text


@pytest.mark.asyncio
async def test_budget_review_prompt_contains_budget():
    result = await resolve_prompt("budget_review", {"budget_pln": "5000"})
    text = result.messages[0].content.text
    assert "5000" in text
    assert result.description == "Monthly budget review"


@pytest.mark.asyncio
async def test_currency_exposure_prompt_renders():
    result = await resolve_prompt("currency_exposure", {})
    assert result.description == "Currency exposure analysis"
    assert len(result.messages) == 1


@pytest.mark.asyncio
async def test_unknown_prompt_raises():
    with pytest.raises(ValueError, match="Unknown prompt"):
        await resolve_prompt("nonexistent", {})
