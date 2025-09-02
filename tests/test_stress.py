# tests/test_stress.py
import asyncio
import statistics
import time
import pytest
from httpx import AsyncClient, ASGITransport

from crypto_converter.api.main import app
from crypto_converter.db import crud


@pytest.mark.asyncio
async def test_convert_stress_latency(db_session):
    """
    Fire a lot of concurrent /convert requests and assert:
      - HTTP 200 for all
      - average latency under a lenient threshold
      - 95th percentile under a lenient threshold
    This is a sanity/stability check, not a microbenchmark.
    """

    # Ensure a fresh live quote exists so we don't trip 'quotes_outdated'
    await crud.save_quote(db_session, "BTC", "USDT", 50000.0)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:

        # Warm-up (build routes, import dependencies etc.)
        r = await ac.get("/convert?amount=1&from=BTC&to=USDT")
        assert r.status_code == 200

        # Stress parameters
        total_requests = 200
        concurrency = 50  # cap to avoid event-loop thrash
        sem = asyncio.Semaphore(concurrency)
        latencies = []

        async def one_call():
            async with sem:
                t0 = time.monotonic()
                resp = await ac.get("/convert?amount=2&from=BTC&to=USDT")
                t1 = time.monotonic()
                latencies.append(t1 - t0)
                assert resp.status_code == 200
                data = resp.json()
                # Quick correctness check
                assert data["rate"] == 50000.0
                assert data["amount_out"] == 100000.0

        # Launch
        await asyncio.gather(*[one_call() for _ in range(total_requests)])

    # Metrics
    latencies.sort()
    avg = statistics.mean(latencies)
    p95 = latencies[int(0.95 * len(latencies)) - 1]

    # Reasonable lenient thresholds for a test environment
    # (adjust if your CI runners are slower)
    assert avg < 0.60, f"Average latency too high: {avg:.3f}s"
    assert p95 < 0.90, f"p95 latency too high: {p95:.3f}s"

    # Optional: print metrics for visibility in CI logs
    print(f"[stress] n={len(latencies)} avg={avg:.3f}s p95={p95:.3f}s")
