import asyncio
import logging
import contextlib
from datetime import datetime
from typing import Dict, Tuple, List

from crypto_converter.consumer.binance import fetch_spot_pairs, subscribe_tickers
from crypto_converter.db.session import AsyncSessionLocal, engine
from crypto_converter.db.models import Base
from crypto_converter.db import crud
from crypto_converter.config import settings

log = logging.getLogger("consumer")

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def chunked(seq: List, n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

async def run_consumer():
    await init_db()

    # Discover spot pairs (base, quote, symbol_lc)
    pairs = await fetch_spot_pairs()
    if not pairs:
        log.warning("No spot pairs discovered from Binance.")
        return

    log.info(f"Discovered {len(pairs)} spot pairs.")

    # Split into batches so we don't exceed streams-per-connection limits
    batches = list(chunked(pairs, settings.MAX_STREAMS_PER_CONN))
    log.info(f"Starting {len(batches)} WS batch connection(s).")

    # Start one task per batch
    tasks = [asyncio.create_task(run_batch(batch)) for batch in batches]
    await asyncio.gather(*tasks)


async def run_batch(batch: List[Tuple[str, str, str]]):
    """
    Maintain latest prices for this batch of symbols and periodically flush to DB.
    """
    latest: Dict[Tuple[str, str], float] = {}
    symbols_lc = [sym for _, _, sym in batch]
    sym_to_pair = {(b + q).upper(): (b, q) for (b, q, _) in batch}

    first_flush_done = False

    async def saver():
        nonlocal first_flush_done
        while True:
            # First flush ASAP once we have any price
            if not first_flush_done:
                if latest:
                    try:
                        async with AsyncSessionLocal() as session:
                            for (base, quote), price in list(latest.items()):
                                await crud.save_quote(session, base, quote, price)
                            await crud.cleanup_old_quotes(session)
                        first_flush_done = True
                    except Exception as e:
                        log.warning(f"Initial batch flush error: {e}")
                await asyncio.sleep(0.01)
                continue

            # Regular periodic flush
            await asyncio.sleep(settings.QUOTE_SAVE_INTERVAL)
            if not latest:
                continue
            try:
                async with AsyncSessionLocal() as session:
                    for (base, quote), price in list(latest.items()):
                        await crud.save_quote(session, base, quote, price)
                    await crud.cleanup_old_quotes(session)
                log.debug(f"Flushed {len(latest)} quotes at {datetime.utcnow().isoformat()}Z")
            except Exception as e:
                log.warning(f"Batch flush error: {e}")

    # Start the saver
    saver_task = asyncio.create_task(saver())

    backoff = 1
    try:
        while True:
            try:
                backoff = 1
                # Continuously read combined ticker stream
                async for msg in subscribe_tickers(symbols_lc):
                    sym_upper = msg.get("s")
                    price_str = msg.get("c")
                    if not sym_upper or not price_str:
                        continue
                    pair = sym_to_pair.get(sym_upper)
                    if not pair:
                        continue
                    try:
                        latest[pair] = float(price_str)
                    except ValueError:
                        continue
                # if we exit the async-for, reconnect
                raise ConnectionError("Combined stream ended")
            except asyncio.CancelledError:
                log.info("Cancellation requested; exiting batch.")
                break
            except Exception as e:
                log.warning(f"Batch stream error: {e}. Reconnecting in {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
    finally:
        saver_task.cancel()
        with contextlib.suppress(Exception):
            await saver_task

