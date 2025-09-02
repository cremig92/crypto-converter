# tests/test_concurrency.py
import asyncio
import pytest
from datetime import datetime, timedelta

from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, func

from crypto_converter.api.main import app
from crypto_converter.db import crud
from crypto_converter.db.models import Quote
from crypto_converter.db.session import AsyncSessionLocal


@pytest.mark.asyncio
async def test_api_concurrent_requests_success(db_session):
    """
    Many concurrent reads should work and return consistent results.
    """
    await crud.save_quote(db_session, "BTC", "USDT", 50000.0)

    transport = ASGITransport(app=app)

    async def call():
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/convert?amount=2&from=BTC&to=USDT")
            assert r.status_code == 200
            data = r.json()
            assert data["rate"] == 50000.0
            assert data["amount_out"] == 100000.0
            return data

    results = await asyncio.gather(*[call() for _ in range(50)])
    # all results should be identical
    assert all(res["rate"] == 50000.0 for res in results)


@pytest.mark.asyncio
async def test_api_concurrent_live_and_historical(db_session):
    """
    Concurrent requests mixing live and historical must route to the correct quote.
    """
    # historical (older) quote
    t_old = datetime.utcnow() - timedelta(minutes=10)
    db_session.add(Quote(base="ETH", quote="USDT", price=1500.0, timestamp=t_old))
    # live (newest) quote
    t_new = datetime.utcnow()
    db_session.add(Quote(base="ETH", quote="USDT", price=1800.0, timestamp=t_new))
    await db_session.commit()

    transport = ASGITransport(app=app)

    async def live():
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get("/convert?amount=1&from=ETH&to=USDT")
            assert r.status_code == 200
            return r.json()["rate"]

    async def historical():
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.get(f"/convert?amount=1&from=ETH&to=USDT&timestamp={t_old.isoformat()}")
            assert r.status_code == 200
            return r.json()["rate"]

    # Run several of each concurrently
    results_live, results_hist = await asyncio.gather(
        asyncio.gather(*[live() for _ in range(20)]),
        asyncio.gather(*[historical() for _ in range(20)]),
    )

    assert all(rate == 1800.0 for rate in results_live)
    assert all(rate == 1500.0 for rate in results_hist)


@pytest.mark.asyncio
async def test_db_concurrent_writes_are_serialized():
    """
    Multiple writers (separate sessions) should serialize and persist without errors.
    """
    async def writer(i: int):
        async with AsyncSessionLocal() as s:
            # slightly different timestamps to avoid same-second collisions
            ts = datetime.utcnow() - timedelta(seconds=i)
            s.add(Quote(base="DOGE", quote="USDT", price=0.1 + i / 1000.0, timestamp=ts))
            await s.commit()

    await asyncio.gather(*[writer(i) for i in range(20)])

    async with AsyncSessionLocal() as s:
        count = (await s.execute(
            select(func.count()).select_from(Quote).where(Quote.base == "DOGE", Quote.quote == "USDT")
        )).scalar_one()
    assert count == 20


@pytest.mark.asyncio
async def test_cleanup_running_while_saving_no_race(monkeypatch):
    """
    Simulate saver writing recent quotes while cleanup runs in parallel; end state must keep only recent rows.
    """
    # Insert some old quotes (8 days ago) that should be removed
    eight_days_ago = datetime.utcnow() - timedelta(days=8)
    async with AsyncSessionLocal() as s:
        s.add_all([
            Quote(base="LTC", quote="USDT", price=70.0, timestamp=eight_days_ago),
            Quote(base="LTC", quote="USDT", price=80.0, timestamp=eight_days_ago),
        ])
        await s.commit()

    # In parallel, write a few recent quotes and run cleanup a few times
    async def writer():
        for p in [90.0, 91.0, 92.0]:
            async with AsyncSessionLocal() as s:
                await crud.save_quote(s, "LTC", "USDT", p)
            await asyncio.sleep(0.02)

    async def cleaner():
        for _ in range(5):
            async with AsyncSessionLocal() as s:
                await crud.cleanup_old_quotes(s)
            await asyncio.sleep(0.01)

    await asyncio.gather(writer(), cleaner())

    # Verify only recent quotes remain
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(Quote).where(Quote.base == "LTC", Quote.quote == "USDT").order_by(Quote.timestamp.asc())
        )).scalars().all()

    assert len(rows) >= 3, "Old quotes should be gone; recent ones should remain"
    assert all(r.timestamp > datetime.utcnow() - timedelta(days=7) for r in rows)
