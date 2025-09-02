import json
import logging
import sys
from datetime import datetime
from typing import Any, Mapping
from crypto_converter.config import settings

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Mapping[str, Any] = {
            "ts": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "service": settings.SERVICE_NAME,
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        payload["module"] = record.module
        payload["funcName"] = record.funcName
        payload["lineno"] = record.lineno
        return json.dumps(payload, ensure_ascii=False)

def setup_logging(component: str) -> None:
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    formatter = JsonFormatter() if settings.LOG_FORMAT.lower() == "json" else logging.Formatter(
        fmt=f"%(asctime)s | %(levelname)s | %(name)s | {component} | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    )
    handler.setFormatter(formatter)
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(handler)
    root.setLevel(level)
    for noisy in ("uvicorn", "uvicorn.error", "uvicorn.access", "aiohttp.access"):
        logging.getLogger(noisy).setLevel(level)
