import sys
import uvicorn
from crypto_converter.utils.logging import setup_logging
from crypto_converter.config import settings

def main():
    if len(sys.argv) < 2:
        print("Usage: python run.py [api|quote-consumer]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "api":
        setup_logging(component="api")
        uvicorn.run(
            "crypto_converter.api.main:app",
            host="0.0.0.0",
            port=8000,
            log_level=settings.LOG_LEVEL.lower(),
            access_log=True,
        )
    elif cmd == "quote-consumer":
        setup_logging(component="consumer")
        import asyncio
        from crypto_converter.consumer.main import run_consumer
        asyncio.run(run_consumer())
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()
