"""SQLAlchemy 2.x ORM models.

``instruments`` is the Kite instrument master; ``ohlc_bars`` holds canonical
**1-minute** OHLC bars and is turned into a TimescaleDB hypertable by the Alembic
migration. Higher timeframes (5/15/60-min) are derived by continuous aggregates,
not stored here, so there is a single source of truth for price data.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all models."""


class Instrument(Base):
    """A tradable instrument from Kite's instrument dump."""

    __tablename__ = "instruments"

    # Kite's numeric token; not auto-generated — it comes from the exchange.
    instrument_token: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    exchange_token: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tradingsymbol: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    exchange: Mapped[str] = mapped_column(String(16))
    segment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    instrument_type: Mapped[str] = mapped_column(String(16))
    lot_size: Mapped[int] = mapped_column(Integer, default=1)
    tick_size: Mapped[float] = mapped_column(Float, default=0.05)
    expiry: Mapped[date | None] = mapped_column(Date, nullable=True)
    strike: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_instruments_exchange_symbol", "exchange", "tradingsymbol"),)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Instrument {self.exchange}:{self.tradingsymbol} ({self.instrument_token})>"


class OHLCBar(Base):
    """A single 1-minute OHLC bar. The hypertable's partitioning column is
    ``time``; it must be part of the primary key (a TimescaleDB requirement)."""

    __tablename__ = "ohlc_bars"

    instrument_token: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("instruments.instrument_token", ondelete="CASCADE"),
        primary_key=True,
    )
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(BigInteger, default=0)

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<OHLCBar {self.instrument_token} @ {self.time} c={self.close}>"
