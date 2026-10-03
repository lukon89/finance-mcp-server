from mcp.types import (
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    TextContent,
)

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

PROMPTS = [
    Prompt(
        name="analyze_spending",
        description="Analyze spending patterns for a given time period",
        arguments=[
            PromptArgument(name="period",   description="Period e.g. 'last month', 'Q3 2026'", required=True),
            PromptArgument(name="focus",    description="Category to focus on (optional)",      required=False),
        ],
    ),
    Prompt(
        name="budget_review",
        description="Monthly budget review with actionable recommendations",
        arguments=[
            PromptArgument(name="budget_pln", description="Monthly budget in PLN", required=False),
        ],
    ),
    Prompt(
        name="currency_exposure",
        description="Analyze currency exposure across accounts",
        arguments=[],
    ),
]


async def resolve_prompt(name: str, arguments: dict) -> GetPromptResult:
    match name:
        case "analyze_spending":
            period = arguments.get("period", "last month")
            focus  = arguments.get("focus", "")
            focus_text = f" Focus particularly on the **{focus}** category." if focus else ""
            return GetPromptResult(
                description=f"Spending analysis — {period}",
                messages=[PromptMessage(role="user", content=TextContent(
                    type="text",
                    text=_ANALYZE_SPENDING_TEMPLATE.format(period=period, focus_text=focus_text),
                ))],
            )

        case "budget_review":
            budget = arguments.get("budget_pln", "10000")
            return GetPromptResult(
                description="Monthly budget review",
                messages=[PromptMessage(role="user", content=TextContent(
                    type="text",
                    text=_BUDGET_REVIEW_TEMPLATE.format(budget=budget),
                ))],
            )

        case "currency_exposure":
            return GetPromptResult(
                description="Currency exposure analysis",
                messages=[PromptMessage(role="user", content=TextContent(
                    type="text",
                    text=_CURRENCY_EXPOSURE_TEMPLATE,
                ))],
            )

        case _:
            raise ValueError(f"Unknown prompt: {name}")
