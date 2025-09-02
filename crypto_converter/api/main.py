import logging
from fastapi import FastAPI, Request
from time import perf_counter
from crypto_converter.api.routes import router

logger = logging.getLogger("api")
app = FastAPI(title="Crypto Converter API")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = perf_counter()
    resp = await call_next(request)
    duration_ms = int((perf_counter() - start) * 1000)
    logger.info(f"{request.method} {request.url.path} -> {resp.status_code} ({duration_ms}ms)")
    return resp

app.include_router(router)
