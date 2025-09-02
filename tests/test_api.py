# tests/test_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timedelta
from sqlalchemy import select, func

from crypto_converter.api.main import app
from crypto_converter.db.models import Quote
from crypto_converter.db import crud


@pytest.mark.asyncio
async def test_convert_success(db_session):
    await crud.save_quote(db_session, "BTC", "USDT", 50000.0)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/convert?amount=2&from=BTC&to=USDT")

    assert resp.status_code == 200
    data = resp.json()
    assert data["amount_out"] == 100000.0
    assert data["rate"] == 50000.0


@pytest.mark.asyncio
async def test_convert_pair_not_found():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/convert?amount=1&from=ETH&to=USD")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Conversion not available for this pair"


@pytest.mark.asyncio
async def test_quotes_outdated(db_session):
    old_quote = Quote(
        base="BTC",
        quote="USDT",
        price=40000.0,
        timestamp=datetime.utcnow() - timedelta(minutes=2),
    )
    db_session.add(old_quote)
    await db_session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/convert?amount=1&from=BTC&to=USDT")

    assert resp.status_code == 400
    assert resp.json()["detail"] == "quotes_outdated"


@pytest.mark.asyncio
async def test_historical_conversion(db_session):
    ts_past = datetime.utcnow() - timedelta(minutes=5)
    old_quote = Quote(
        base="ETH",
        quote="USDT",
        price=2000.0,
        timestamp=ts_past,
    )
    db_session.add(old_quote)
    await db_session.commit()

    query_ts = ts_past.isoformat()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(f"/convert?amount=3&from=ETH&to=USDT&timestamp={query_ts}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["rate"] == 2000.0
    assert data["amount_out"] == 6000.0


@pytest.mark.asyncio
async def test_cleanup_removes_quotes_older_than_retention(db_session):
    # Insert one old (8 days) and one recent (1 day) quote
    eight_days_ago = datetime.utcnow() - timedelta(days=8)
    one_day_ago = datetime.utcnow() - timedelta(days=1)

    old_q = Quote(base="BTC", quote="USDT", price=10000.0, timestamp=eight_days_ago)
    recent_q = Quote(base="BTC", quote="USDT", price=20000.0, timestamp=one_day_ago)

    db_session.add_all([old_q, recent_q])
    await db_session.commit()

    # Run cleanup (uses settings.QUOTE_RETENTION_DAYS == 7)
    await crud.cleanup_old_quotes(db_session)

    # Verify only the recent quote remains
    count = (await db_session.execute(select(func.count()).select_from(Quote))).scalar_one()
    assert count == 1

    remaining = (await db_session.execute(
        select(Quote).order_by(Quote.timestamp.desc())
    )).scalars().all()
    assert len(remaining) == 1
    assert remaining[0].timestamp == one_day_ago
    assert remaining[0].price == 20000.0


@pytest.mark.asyncio
async def test_inverts_reverse_pair(db_session):
    # Save DOGE/USDT = 0.2 → implies USDT/DOGE = 5.0
    await crud.save_quote(db_session, "DOGE", "USDT", 0.2)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/convert", params={"amount": 10, "from": "USDT", "to": "DOGE"})
    assert r.status_code == 200
    data = r.json()
    assert abs(data["rate"] - 5.0) < 1e-9
    assert data["amount_out"] == 50.0
    assert data["inverted"] is True