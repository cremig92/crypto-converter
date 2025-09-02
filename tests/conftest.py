# tests/conftest.py
import os
import pathlib
import importlib
import pytest_asyncio

# 1) Point to a test-only DB BEFORE importing app modules
TEST_DIR = pathlib.Path(__file__).parent / "test_data"
TEST_DIR.mkdir(parents=True, exist_ok=True)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(TEST_DIR / 'quotes_test.db').as_posix()}"

# 2) Reload app modules so they pick up the test DB URL
import crypto_converter.config as _config
importlib.reload(_config)
import crypto_converter.db.session as _dbsession
importlib.reload(_dbsession)

from crypto_converter.db.session import engine, AsyncSessionLocal
from crypto_converter.db.models import Base

# 3) Function-scoped isolation: drop/create tables before EACH test
@pytest_asyncio.fixture(autouse=True, scope="function")
async def reset_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield

# 4) Async DB session fixture
@pytest_asyncio.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session
