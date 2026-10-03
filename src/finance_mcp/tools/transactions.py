from typing import Literal

import aiosqlite

from finance_mcp.config import settings

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

Category = Literal["Food", "Transport", "Entertainment", "Utilities", "Shopping", "Healthcare", "Salary", "Freelance"]
Period   = Literal["last_7_days", "last_30_days", "last_90_days", "this_month", "last_month"]
GroupBy  = Literal["category", "account", "month"]


async def search_transactions(
    query:      str | None = None,
    date_from:  str | None = None,
    date_to:    str | None = None,
    category:   Category | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    account:    str | None = None,
    limit:      int = 20,
) -> str:
    """Search and filter financial transactions. Returns a markdown table."""
    conditions: list[str] = []
    params: list[str | float | int] = []

    if query:
        conditions.append("description LIKE ?"); params.append(f"%{query}%")
    if date_from:
        conditions.append("date >= ?"); params.append(date_from)
    if date_to:
        conditions.append("date <= ?"); params.append(date_to)
    if category:
        conditions.append("category = ?"); params.append(category)
    if min_amount is not None:
        conditions.append("amount >= ?"); params.append(min_amount)
    if max_amount is not None:
        conditions.append("amount <= ?"); params.append(max_amount)
    if account:
        conditions.append("account = ?"); params.append(account)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    limit = min(limit, 100)

    async with aiosqlite.connect(settings.db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT * FROM transactions {where} ORDER BY date DESC LIMIT ?",
            params + [limit],
        ) as cur:
            rows = list(await cur.fetchall())

    if not rows:
        return "No transactions found."

    header = "| Date | Description | Amount | Currency | Category | Account |\n|---|---|---|---|---|---|"
    lines  = [
        f"| {r['date']} | {r['description']} | {r['amount']:+.2f} | {r['currency']} | {r['category']} | {r['account']} |"
        for r in rows
    ]
    total = sum(r["amount"] for r in rows)
    return f"**{len(rows)} transactions** (sum: {total:+.2f})\n\n{header}\n" + "\n".join(lines)


async def spending_summary(
    period:         Period = "last_30_days",
    group_by:       GroupBy = "category",
    include_income: bool = False,
) -> str:
    """Aggregated spending grouped by category, account, or month."""
    period_sql = _PERIOD_SQL[period]
    group_col  = _GROUP_COL[group_by]
    income_sql = "" if include_income else "AND amount < 0"

    async with aiosqlite.connect(settings.db_path) as db, db.execute(
        f"""SELECT {group_col} AS label, SUM(amount) AS total, COUNT(*) AS cnt
            FROM transactions
            WHERE {period_sql} {income_sql}
            GROUP BY {group_col}
            ORDER BY total ASC""",
    ) as cur:
        rows = await cur.fetchall()

    if not rows:
        return f"No data for period: {period}"

    grand  = sum(r[1] for r in rows)
    header = f"| {group_by.title()} | Total | Transactions |\n|---|---|---|"
    lines  = [f"| {r[0]} | {r[1]:+.2f} | {r[2]} |" for r in rows]
    return f"**Spending — {period}** (by {group_by})\nGrand total: **{grand:+.2f}**\n\n{header}\n" + "\n".join(lines)
