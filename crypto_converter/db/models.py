from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import String, Float, DateTime, Integer
from datetime import datetime

Base = declarative_base()

class Quote(Base):
    __tablename__ = "quotes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    base: Mapped[str] = mapped_column(String, index=True)
    quote: Mapped[str] = mapped_column(String, index=True)
    price: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True, default=datetime.utcnow)
