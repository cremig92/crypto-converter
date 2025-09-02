from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./quotes.db"
    BINANCE_WS_URL: str = "wss://stream.binance.com:9443/ws"
    QUOTE_SAVE_INTERVAL: int = 30
    QUOTE_RETENTION_DAYS: int = 7
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "text"
    SERVICE_NAME: str = "crypto-converter"

    SUPPORTED_QUOTES: str = "USDT,USDC"  # comma-separated; set to "" to include ALL spot pairs
    MAX_STREAMS_PER_CONN: int = 800  # Binance combined stream supports up to 1024; we stay under
    SYMBOL_REFRESH_MINUTES: int = 360  # refresh spot symbol list every 6 hours

    model_config = ConfigDict(env_file=".env")

settings = Settings()
