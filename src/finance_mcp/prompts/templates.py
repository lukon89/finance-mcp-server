_ANALYZE_SPENDING_TEMPLATE = """
Please analyze my spending for the period: **{period}**.{focus_text}

Use the following tools:
1. `get_spending_summary` with the appropriate period, group_by="category"
2. `search_transactions` to find the largest individual expenses

The report should include:
- Spending breakdown by category (table)
- Top 5 largest transactions
- 3 concrete recommendations on how to reduce costs
- Trend assessment (am I spending more or less than usual)
""".strip()

_BUDGET_REVIEW_TEMPLATE = """
Do a full budget review for the current month. My budget: **{budget}/month**.

Steps:
1. Use `get_spending_summary` with period="this_month", group_by="category"
2. Use `search_transactions` with date_from=first day of the month

Show me:
- Budget vs actual spending per category
- Month-end forecast (if the current pace continues)
- Which categories are over budget and which have headroom
- Whether I'm on track to save anything this month
""".strip()

_CURRENCY_EXPOSURE_TEMPLATE = """
Analyze my currency exposure across all accounts.

Steps:
1. `search_transactions` with account="usd-account" — income and expenses in USD
2. `get_exchange_rate` to convert USD to the base currency
3. Compare with base currency accounts

Tell me:
- What percentage of my income is in foreign currencies
- How a ±10% exchange rate change would affect my financial position
- Whether hedging currency risk makes sense
""".strip()


async def analyze_spending(period: str, focus: str = "") -> str:
    """Analyze spending patterns for a given time period."""
    focus_text = f" Focus particularly on the **{focus}** category." if focus else ""
    return _ANALYZE_SPENDING_TEMPLATE.format(period=period, focus_text=focus_text)


async def budget_review(budget_pln: str = "10000") -> str:
    """Monthly budget review with actionable recommendations."""
    return _BUDGET_REVIEW_TEMPLATE.format(budget=budget_pln)


async def currency_exposure() -> str:
    """Analyze currency exposure across accounts."""
    return _CURRENCY_EXPOSURE_TEMPLATE
