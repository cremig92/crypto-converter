from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import Optional
from crypto_converter.db.session import get_session
from crypto_converter.db import crud

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "ok"}

@router.get("/convert")
async def convert_currency(
    amount: float = Query(..., gt=0),
    from_currency: str = Query(..., alias="from", min_length=2, max_length=10),
    to_currency: str = Query(..., alias="to", min_length=2, max_length=10),
    timestamp: Optional[datetime] = Query(None),
    session: AsyncSession = Depends(get_session)
):
    base = from_currency.upper()
    quote = to_currency.upper()

    # 1) Try direct quote
    if timestamp:
        q = await crud.get_quote_at(session, base, quote, timestamp)
    else:
        q = await crud.get_latest_quote(session, base, quote)

    inverted = False

    # 2) If not found, try reverse and invert
    if not q:
        rev_base, rev_quote = quote, base
        if timestamp:
            q = await crud.get_quote_at(session, rev_base, rev_quote, timestamp)
        else:
            q = await crud.get_latest_quote(session, rev_base, rev_quote)
        if q:
            if q.price == 0:
                raise HTTPException(status_code=400, detail="invalid_quote_zero_price")
            q.price = 1.0 / q.price
            inverted = True

    if not q:
        raise HTTPException(status_code=404, detail="Conversion not available for this pair")

    # Freshness check only for "latest"
    if not timestamp:
        if datetime.utcnow() - q.timestamp > timedelta(minutes=1):
            raise HTTPException(status_code=400, detail="quotes_outdated")

    converted_amount = amount * q.price
    return {
        "base": base,
        "quote": quote,
        "rate": q.price,
        "amount_in": amount,
        "amount_out": converted_amount,
        "timestamp": q.timestamp,
        "inverted": inverted,
    }
