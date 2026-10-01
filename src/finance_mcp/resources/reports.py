import aiosqlite
from datetime import datetime

from finance_mcp.config import settings


async def get_recent_transactions(limit: int = 50) -> str:
    """Last 30 days of transactions as a markdown table."""
    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            "SELECT date, description, amount, currency, category "
            "FROM transactions WHERE date >= date('now', '-30 days') "
            "ORDER BY date DESC LIMIT ?",
            (limit,),
        ) as cur:
            rows = await cur.fetchall()

    if not rows:
        return "No transactions in the last 30 days."

    total = sum(r[2] for r in rows)
    header = "| Date | Description | Amount | Currency | Category |\n|---|---|---|---|---|"
    lines  = [f"| {r[0]} | {r[1]} | {r[2]:+.2f} | {r[3]} | {r[4]} |" for r in rows]
    return f"# Recent Transactions (Last 30 Days)\n**Total: {total:+.2f} PLN | Count: {len(rows)}**\n\n{header}\n" + "\n".join(lines)


async def get_monthly_report(month_spec: str) -> str:
    """
    Monthly P&L report as markdown.
    month_spec: 'latest' or 'YYYY-MM'
    """
    if month_spec == "latest":
        month_spec = datetime.today().strftime("%Y-%m")

    async with aiosqlite.connect(settings.db_path) as db:
        async with db.execute(
            "SELECT category, SUM(amount) AS total, COUNT(*) AS cnt "
            "FROM transactions WHERE strftime('%Y-%m', date) = ? "
            "GROUP BY category ORDER BY total ASC",
            (month_spec,),
        ) as cur:
            cats = await cur.fetchall()

        async with db.execute(
            "SELECT date, description, amount FROM transactions "
            "WHERE strftime('%Y-%m', date) = ? AND amount < 0 "
            "ORDER BY amount ASC LIMIT 5",
            (month_spec,),
        ) as cur:
            top5 = await cur.fetchall()

    if not cats:
        return f"No data for {month_spec}."

    income   = sum(r[1] for r in cats if r[1] > 0)
    expenses = sum(r[1] for r in cats if r[1] < 0)
    net      = income + expenses

    cat_rows = "\n".join(f"| {r[0]} | {r[1]:+.2f} | {r[2]} |" for r in cats)
    exp_rows = "\n".join(f"| {r[0]} | {r[1]} | {r[2]:+.2f} |" for r in top5)

    return f"""# Monthly Report — {month_spec}

## Summary
| | PLN |
|---|---|
| Income | **{income:+.2f}** |
| Expenses | **{expenses:+.2f}** |
| Net | **{net:+.2f}** |

## By Category
| Category | Total | Transactions |
|---|---|---|
{cat_rows}

## Top 5 Expenses
| Date | Description | Amount |
|---|---|---|
{exp_rows}
"""
