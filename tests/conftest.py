import pytest
from finance_mcp import config as cfg_module
from finance_mcp.config import Settings


@pytest.fixture(autouse=True)
async def isolated_db(tmp_path, monkeypatch):
    """
    Each test gets its own SQLite file.
    monkeypatch replaces settings.db_path before init_db is called.
    """
    db_path = str(tmp_path / "test.db")
    # Patch the singleton settings object used everywhere via import
    monkeypatch.setattr(cfg_module.settings, "db_path", db_path)
    # Also patch the module-level settings in sub-modules that may have
    # cached a reference at import time
    from finance_mcp.tools import transactions, exchange
    monkeypatch.setattr(transactions.settings, "db_path", db_path)

    from finance_mcp.db.setup import init_db
    await init_db()
    yield db_path
