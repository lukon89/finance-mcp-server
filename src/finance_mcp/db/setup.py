import random
import aiosqlite
import structlog
from datetime import datetime, timedelta, timezone
from finance_mcp.config import settings

log = structlog.get_logger()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT    NOT NULL,
    description TEXT    NOT NULL,
    amount      REAL    NOT NULL,
    currency    TEXT    NOT NULL DEFAULT 'PLN',
    category    TEXT    NOT NULL,
    account     TEXT    NOT NULL DEFAULT 'main',
    tags        TEXT    DEFAULT ''
);
"""

_CATEGORIES = ["Food", "Transport", "Entertainment", "Utilities", "Shopping", "Healthcare"]
_MERCHANTS = {
    "Food":          ["Biedronka", "Lidl", "Żabka", "McDonalds", "Sushi Wawa", "Pizza Portal"],
    "Transport":     ["Bolt", "Uber", "PKP Intercity", "MPK Kraków", "Shell", "BP"],
    "Entertainment": ["Netflix", "Spotify", "Steam", "Cinema City", "HBO Max"],
    "Utilities":     ["Orange Polska", "PGNiG", "Tauron", "Allegro"],
    "Shopping":      ["Zalando", "H&M", "Zara", "Amazon PL", "Media Markt"],
    "Healthcare":    ["Medicover", "LuxMed", "Apteka Dr. Max"],
}


async def init_db() -> None:
    """Create schema and seed with sample data if the DB is empty."""
    async with aiosqlite.connect(settings.db_path) as db:
        await db.executescript(_SCHEMA)
        await db.commit()

        async with db.execute("SELECT COUNT(*) FROM transactions") as cur:
            (count,) = await cur.fetchone()

        if count == 0:
            log.info("db_empty_seeding", db_path=settings.db_path)
            await _seed(db)
        else:
            log.info("db_ready", db_path=settings.db_path, transactions=count)


async def _seed(db: aiosqlite.Connection) -> None:
    today = datetime.now(timezone.utc)
    rows = []

    # Daily expenses for last 6 months
    for day_offset in range(180):
        date = (today - timedelta(days=day_offset)).strftime("%Y-%m-%d")
        for _ in range(random.randint(1, 4)):
            cat = random.choice(_CATEGORIES)
            merchant = random.choice(_MERCHANTS[cat])
            amount = -round(random.uniform(8, 350), 2)
            rows.append((date, merchant, amount, "PLN", cat, "main", ""))

    # Monthly salary + freelance income
    for i in range(6):
        month_start = (today.replace(day=1) - timedelta(days=30 * i)).strftime("%Y-%m-%d")
        rows.append((month_start, "Pracodawca Sp. z o.o.", 28_000.0,  "PLN", "Salary",   "main",        "b2b,income"))
        rows.append((month_start, "Kalepa Inc",           5_000.0,   "USD", "Freelance","usd-account", "freelance,income"))

    await db.executemany(
        "INSERT INTO transactions (date, description, amount, currency, category, account, tags) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    await db.commit()
    log.info("db_seeded", rows=len(rows))
