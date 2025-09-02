# tests/test_discovery_batch.py
import asyncio
import time
import pytest
from sqlalchemy import select, func
from crypto_converter.db.models import Quote

@pytest.mark.asyncio
async def test_run_batch_flushes_multiple_pairs(monkeypatch):
    from crypto_converter.consumer import main as consumer_main
    # make sure tables exist
    await consumer_main.init_db()

    # fast interval
    monkeypatch.setattr(consumer_main.settings, "QUOTE_SAVE_INTERVAL", 0.05)

    async def fake_subscribe_tickers(symbols_lc):
        assert set(symbols_lc) == {"btcusdt", "ethusdt"}
        end = time.monotonic() + 0.35
        p_btc, p_eth = 50000.0, 1800.0
        while time.monotonic() < end:
            yield {"s": "BTCUSDT", "c": f"{p_btc:.2f}"}
            yield {"s": "ETHUSDT", "c": f"{p_eth:.2f}"}
            p_btc += 1.0
            p_eth += 0.5
            await asyncio.sleep(0.01)

    monkeypatch.setattr(
        "crypto_converter.consumer.main.subscribe_tickers",
        fake_subscribe_tickers,
        raising=True,
    )

    batch = [("BTC", "USDT", "btcusdt"), ("ETH", "USDT", "ethusdt")]
    task = asyncio.create_task(consumer_main.run_batch(batch))

    # poll up to 1s for rows to appear
    async def counts():
        from crypto_converter.db.session import AsyncSessionLocal
        async with AsyncSessionLocal() as s:
            btc = (await s.execute(
                select(func.count()).select_from(Quote).where(Quote.base=="BTC", Quote.quote=="USDT")
            )).scalar_one()
            eth = (await s.execute(
                select(func.count()).select_from(Quote).where(Quote.base=="ETH", Quote.quote=="USDT")
            )).scalar_one()
            return btc, eth

    ok = False
    for _ in range(20):  # 20*50ms = 1s
        await asyncio.sleep(0.05)
        btc_count, eth_count = await counts()
        if btc_count >= 3 and eth_count >= 3:
            ok = True
            break

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert ok, f"Expected >=3 rows per pair, got BTC={btc_count}, ETH={eth_count}"


def test_chunked_batches_respect_stream_limit(monkeypatch):
    from crypto_converter.consumer import main as consumer_main
    monkeypatch.setattr(consumer_main.settings, "MAX_STREAMS_PER_CONN", 800)

    n = 1200
    pairs = [(f"ASSET{i}", "USDT", f"asset{i}usdt") for i in range(n)]
    batches = list(consumer_main.chunked(pairs, consumer_main.settings.MAX_STREAMS_PER_CONN))

    assert len(batches) == 2
    assert len(batches[0]) == 800
    assert len(batches[1]) == 400
