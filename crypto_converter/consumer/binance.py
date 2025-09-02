import aiohttp
import json
from typing import AsyncGenerator, Iterable, List, Tuple

from crypto_converter.config import settings

API_BASE = "https://api.binance.com"
BINANCE_WS_URL = settings.BINANCE_WS_URL

# --------- REST: discover spot pairs ----------
async def fetch_spot_pairs() -> List[Tuple[str, str, str]]:
    """
    Returns a list of (base, quote, symbol_lc) for all SPOT markets that are TRADING.
    If SUPPORTED_QUOTES is set, only include those quote assets.
    """
    url = f"{API_BASE}/api/v3/exchangeInfo"
    filt = {q.strip().upper() for q in settings.SUPPORTED_QUOTES.split(",") if q.strip()}  # may be empty

    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as s:
        async with s.get(url) as r:
            r.raise_for_status()
            data = await r.json()

    pairs: List[Tuple[str, str, str]] = []
    for sym in data.get("symbols", []):
        status_ok = sym.get("status") == "TRADING"
        spot_ok = ("SPOT" in sym.get("permissions", [])) or sym.get("isSpotTradingAllowed", False)
        if not (status_ok and spot_ok):
            continue
        base = sym["baseAsset"].upper()
        quote = sym["quoteAsset"].upper()
        if filt and quote not in filt:
            continue
        symbol_lc = (base + quote).lower()
        pairs.append((base, quote, symbol_lc))
    return pairs

# --------- WS: combined stream for many tickers ----------
async def subscribe_tickers(symbols_lc: Iterable[str]) -> AsyncGenerator[dict, None]:
    """
    Subscribe to a combined stream of ticker updates for many symbols.
    Yields raw messages with fields including 's' (SYMBOL) and 'c' (last price).
    """
    streams = "/".join(f"{sym}@ticker" for sym in symbols_lc)
    url = f"{BINANCE_WS_URL}/stream?streams={streams}"

    timeout = aiohttp.ClientTimeout(total=None, sock_read=90)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # Heartbeat every 15s and close if no frames for 45s
        async with session.ws_connect(url, heartbeat=15, receive_timeout=45) as ws:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    payload = json.loads(msg.data)
                    # Combined stream wraps the payload under 'data'
                    data = payload.get("data") or payload
                    yield data
                elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                    break
