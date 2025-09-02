# 🚀 Crypto Converter Service

A **real-time cryptocurrency conversion platform** built with **FastAPI, SQLAlchemy, and WebSockets**, powered by **Binance spot market data**.  

The system is designed as two services:

- **Consumer** → streams live quotes from Binance, stores them in a database, and maintains historical data.  
- **API** → exposes endpoints for currency conversion at the latest or historical rates.  

This separation of concerns makes the system scalable, resilient, and easy to extend.  

---

## ✨ Features

- 📡 **Live Data Ingestion**  
  - Subscribes to Binance **combined WebSocket streams** for all supported trading pairs.  
  - Supports batching to respect Binance’s **1024 streams per connection** limit.  
  - Continuously saves the latest prices to the database at a configurable interval.

- 🔄 **Conversion API**  
  - `GET /convert` → Convert between currencies.  
  - Supports both **direct pairs** (e.g., DOGE → USDT) and **reverse pairs** (e.g., USDT → DOGE, computed as the inverse).  
  - Allows **historical lookups** at a given UTC timestamp.  
  - Ensures quotes are **fresh** (default: max age 1 minute for latest requests).

- 🧹 **Data Retention & Cleanup**  
  - Old quotes are automatically removed (default: older than 7 days).  
  - Keeps the DB lightweight and performant while retaining enough history for analysis.

- ⚙️ **Configurable Settings** (via `.env`)  
  - Supported quote currencies (`SUPPORTED_QUOTES`)  
  - Database backend (`DATABASE_URL`)  
  - Flush interval (`QUOTE_SAVE_INTERVAL`)  
  - Retention period (`QUOTE_RETENTION_DAYS`)  
  - Log level (`LOG_LEVEL`)  
  - Binance WebSocket endpoint (`BINANCE_WS_URL`)

- 🧪 **Robust Testing**  
  - Unit and integration tests with `pytest-asyncio`.  
  - Binance WebSockets are mocked with `monkeypatch` for reproducibility.  
  - Tests cover API endpoints, consumer batch flushing, and DB cleanup.

---

## 🏗 Architecture

```
crypto-converter/
├── crypto_converter/
│   ├── api/          # FastAPI service (HTTP API)
│   ├── consumer/     # Binance consumer (WebSocket + DB writer)
│   ├── db/           # SQLAlchemy async models, sessions, CRUD
│   ├── config.py     # Settings management (Pydantic)
│   └── ...
├── tests/            # Unit + integration tests
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── .env
└── README.md
```

- **Database**: SQLite (async via `aiosqlite`)  
- **WebSockets**: Binance combined streams (`/stream?streams=`)  
- **Services**: API + Consumer run independently (Docker Compose)  

---

## ⚙️ Configuration

`.env` example:

```env
# Database
DATABASE_URL=sqlite+aiosqlite:///./data/quotes.db

# Binance WS base (do not include /ws)
BINANCE_WS_URL=wss://stream.binance.com:9443

# Quote assets to track (comma-separated, empty = all)
SUPPORTED_QUOTES=USDT,USDC

# Interval in seconds to flush latest prices
QUOTE_SAVE_INTERVAL=30

# Retain quotes for N days
QUOTE_RETENTION_DAYS=7

# Logging
LOG_LEVEL=INFO
```

---

## 🚀 Running the Project

### 1. Clone & configure
```bash
git clone https://github.com/cremig92/crypto-converter.git
cd crypto-converter
```

### 2. Start services
Start docker, then: 
```bash
docker compose up --build
```

- **API** → [http://localhost:8000](http://localhost:8000)  
- **Consumer** → runs in background, streaming live quotes  

---

## 🚀 Usage Examples

### Health check
Verify the API is running:
```bash
curl http://localhost:8000/health
```

**Example response:**
```json
{"status": "ok"}
```

---

### Latest conversion
Convert 10 DOGE → USDT:
```bash
curl "http://localhost:8000/convert?amount=10&from=DOGE&to=USDT"
```

**Example response:**
```json
{
  "from": "DOGE",
  "to": "USDT",
  "amount_in": 10.0,
  "rate": 0.0735,
  "amount_out": 0.735,
  "timestamp": "2025-09-02T12:30:45Z",
  "inverted": false
}
```

---

### Reverse conversion
Convert 10 USDT → DOGE (API inverts the DOGE/USDT price):
```bash
curl "http://localhost:8000/convert?amount=10&from=USDT&to=DOGE"
```

**Example response:**
```json
{
  "from": "USDT",
  "to": "DOGE",
  "amount_in": 10.0,
  "rate": 13.6054,
  "amount_out": 136.054,
  "timestamp": "2025-09-02T12:30:45Z",
  "inverted": true
}
```

---

### Historical conversion
Convert 1 BTC → USDT as of 5 minutes ago:

**Linux:**
```bash
curl "http://localhost:8000/convert?amount=1&from=BTC&to=USDT&timestamp=$(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%S)"
```

**macOS:**
```bash
curl "http://localhost:8000/convert?amount=1&from=BTC&to=USDT&timestamp=$(date -u -v-5M +%Y-%m-%dT%H:%M:%S)"
```

**Example response:**
```json
{
  "from": "BTC",
  "to": "USDT",
  "amount_in": 1.0,
  "rate": 64250.11,
  "amount_out": 64250.11,
  "timestamp": "2025-09-02T12:25:45Z",
  "inverted": false
}
```

---

### Error: outdated quote
If the latest quote is older than 1 minute:
```bash
curl "http://localhost:8000/convert?amount=10&from=ADA&to=USDT"
```

**Example response:**
```json
{
  "detail": "quotes_outdated"
}
```

---

### Error: unsupported pair
If the pair doesn’t exist (e.g., ABC/XYZ):
```bash
curl "http://localhost:8000/convert?amount=10&from=ABC&to=XYZ"
```

**Example response:**
```json
{
  "detail": "Conversion not available for this pair"
}
```

---

## 🧪 Testing

This project uses **pytest** with **pytest-asyncio** to cover both **unit** and **integration** scenarios.  

### Test Categories

1. **Unit Tests**
   - CRUD logic (save, fetch, cleanup quotes)  
   - Inversion logic (`DOGE/USDT` → supports `USDT/DOGE`)  
   - Retention policy (>7 days cleanup)  

2. **API Integration Tests**
   - `/health` endpoint  
   - `/convert` latest and historical requests  
   - Error cases: outdated quotes, unsupported pairs  
   - Concurrency: multiple simultaneous conversion requests  

3. **Consumer Tests**
   - Batch flushing of multiple pairs  
   - First-flush logic (no long wait for first DB write)  
   - Reconnect logic when streams fail  

4. **Async Behavior**
   - Saver and reader tasks run concurrently without blocking  
   - Graceful cancellation of consumer tasks  

### Test Environment

- Isolated SQLite DB for every test run  
- `conftest.py` ensures function-scoped fixtures  
- Binance WebSockets are mocked (deterministic + no network required)  

### Run Tests

Cd to the project folder, then: 

```bash
pip install -r requirements.txt
python -m pytest -v  
```
---
