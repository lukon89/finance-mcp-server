import random

import pytest
from finance_mcp import config as cfg_module


@pytest.fixture(autouse=True)
async def isolated_db(tmp_path, monkeypatch):
    """
    Each test gets its own SQLite file with a deterministic seed so that
    category/merchant distribution is stable across runs.
    monkeypatch replaces settings.db_path before init_db is called.
    """
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(cfg_module.settings, "db_path", db_path)

    from finance_mcp.tools import transactions
    monkeypatch.setattr(transactions.settings, "db_path", db_path)

    # Clear the exchange rate cache so tests don't share cached HTTP responses
    from finance_mcp.tools.exchange import _cache
    _cache.clear()

    # Fixed seed makes the random seeder deterministic — every test run
    # produces the same category/merchant distribution.
    random.seed(42)

    from finance_mcp.db.setup import init_db
    await init_db()
    yield db_path
