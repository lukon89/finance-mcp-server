import aiosqlite
from mcp.types import TextContent, Tool

from finance_mcp.config import settings
from finance_mcp.tools import ToolRegistration

SEARCH_TOOL = Tool(
    name="search_transactions",
    description="Search and filter financial transactions. Returns markdown table.",
    inputSchema={
        "type": "object",
        "properties": {
            "query":      {"type": "string",  "description": "Text to search in description"},
            "date_from":  {"type": "string",  "description": "Start date YYYY-MM-DD"},
            "date_to":    {"type": "string",  "description": "End date YYYY-MM-DD"},
            "category":   {"type": "string",  "enum": ["Food","Transport","Entertainment","Utilities","Shopping","Healthcare","Salary","Freelance"]},
            "min_amount": {"type": "number",  "description": "Minimum amount (negative = expenses)"},
            "max_amount": {"type": "number",  "description": "Maximum amount"},
            "account":    {"type": "string",  "description": "Account name (main, usd-account…)"},
            "limit":      {"type": "integer", "description": "Max rows to return", "default": 20, "maximum": 100},
        },
    },
)

SUMMARY_TOOL = Tool(
    name="get_spending_summary",
    description="Aggregated spending grouped by category, account, or month.",
    inputSchema={
        "type": "object",
        "properties": {
            "period":   {"type": "string", "enum": ["last_7_days","last_30_days","last_90_days","this_month","last_month"], "default": "last_30_days"},
            "group_by": {"type": "string", "enum": ["category","account","month"], "default": "category"},
            "include_income": {"type": "boolean", "default": False},
        },
    },
)

_PERIOD_SQL = {
    "last_7_days":  "date >= date('now', '-7 days')",
    "last_30_days": "date >= date('now', '-30 days')",
    "last_90_days": "date >= date('now', '-90 days')",
    "this_month":   "strftime('%Y-%m', date) = strftime('%Y-%m', 'now')",
    "last_month":   "strftime('%Y-%m', date) = strftime('%Y-%m', 'now', '-1 month')",
}
_GROUP_COL = {
    "category": "category",
    "account":  "account",
    "month":    "strftime('%Y-%m', date)",
}


async def handle_search_transactions(args: dict) -> list[TextContent]:
    conditions, params = [], []

    if q := args.get("query"):
        conditions.append("description LIKE ?"); params.append(f"%{q}%")
    if df := args.get("date_from"):
        conditions.append("date >= ?"); params.append(df)
    if dt := args.get("date_to"):
        conditions.append("date <= ?"); params.append(dt)
    if cat := args.get("category"):
        conditions.append("category = ?"); params.append(cat)
    if (mn := args.get("min_amount")) is not None:
        conditions.append("amount >= ?"); params.append(mn)
    if (mx := args.get("max_amount")) is not None:
        conditions.append("amount <= ?"); params.append(mx)
    if acc := args.get("account"):
        conditions.append("account = ?"); params.append(acc)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    limit = min(int(args.get("limit", 20)), 100)

    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT * FROM transactions {where} ORDER BY date DESC LIMIT ?",
            params + [limit],
        ) as cur:
            rows = list(await cur.fetchall())

    if not rows:
        return [TextContent(type="text", text="No transactions found.")]

    header = "| Date | Description | Amount | Currency | Category | Account |\n|---|---|---|---|---|---|"
    lines  = [
        f"| {r['date']} | {r['description']} | {r['amount']:+.2f} | {r['currency']} | {r['category']} | {r['account']} |"
        for r in rows
    ]
    total = sum(r["amount"] for r in rows)
    text  = f"**{len(rows)} transactions** (sum: {total:+.2f})\n\n{header}\n" + "\n".join(lines)
    return [TextContent(type="text", text=text)]


async def handle_spending_summary(args: dict) -> list[TextContent]:
    period         = args.get("period", "last_30_days")
    group_by       = args.get("group_by", "category")
    include_income = args.get("include_income", False)

    if period not in _PERIOD_SQL:
        raise ValueError(f"Invalid period: {period!r}. Valid: {list(_PERIOD_SQL)}")
    if group_by not in _GROUP_COL:
        raise ValueError(f"Invalid group_by: {group_by!r}. Valid: {list(_GROUP_COL)}")

    period_sql  = _PERIOD_SQL[period]
    group_col   = _GROUP_COL[group_by]
    income_sql  = "" if include_income else "AND amount < 0"

    async with aiosqlite.connect(settings.db_path) as db, db.execute(
        f"""SELECT {group_col} AS label, SUM(amount) AS total, COUNT(*) AS cnt
                FROM transactions
                WHERE {period_sql} {income_sql}
                GROUP BY {group_col}
                ORDER BY total ASC""",
    ) as cur:
        rows = await cur.fetchall()

    if not rows:
        return [TextContent(type="text", text=f"No data for period: {period}")]

    grand = sum(r[1] for r in rows)
    header = f"| {group_by.title()} | Total | Transactions |\n|---|---|---|"
    lines  = [f"| {r[0]} | {r[1]:+.2f} | {r[2]} |" for r in rows]
    text   = f"**Spending — {period}** (by {group_by})\nGrand total: **{grand:+.2f}**\n\n{header}\n" + "\n".join(lines)
    return [TextContent(type="text", text=text)]


# ── Registration ──────────────────────────────────────────────────────────────

TOOLS: list[ToolRegistration] = [
    (SEARCH_TOOL, handle_search_transactions),
    (SUMMARY_TOOL, handle_spending_summary),
]
