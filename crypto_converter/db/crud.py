from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from crypto_converter.db.models import Quote
from crypto_converter.config import settings

async def save_quote(session: AsyncSession, base: str, quote: str, price: float):
    q = Quote(base=base, quote=quote, price=price, timestamp=datetime.utcnow())
    session.add(q)
    await session.commit()

async def get_latest_quote(session: AsyncSession, base: str, quote: str):
    stmt = select(Quote).where(Quote.base == base, Quote.quote == quote).order_by(Quote.timestamp.desc()).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def get_quote_at(session: AsyncSession, base: str, quote: str, ts: datetime):
    stmt = select(Quote).where(Quote.base == base, Quote.quote == quote, Quote.timestamp <= ts).order_by(Quote.timestamp.desc()).limit(1)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def cleanup_old_quotes(session: AsyncSession):
    cutoff = datetime.utcnow() - timedelta(days=settings.QUOTE_RETENTION_DAYS)
    stmt = delete(Quote).where(Quote.timestamp < cutoff)
    await session.execute(stmt)
    await session.commit()
