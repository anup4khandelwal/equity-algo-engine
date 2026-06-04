"""Repositories: the only place that issues SQL for our tables.

Upserts use PostgreSQL's ``INSERT ... ON CONFLICT`` so re-running a backfill is
idempotent (existing rows are refreshed rather than duplicated).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .models import Instrument, OHLCBar


class InstrumentRepository:
    """Read/write access to the instrument master."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_many(self, records: list[dict[str, Any]]) -> int:
        if not records:
            return 0
        stmt = pg_insert(Instrument).values(records)
        update_cols = {
            col.name: stmt.excluded[col.name]
            for col in Instrument.__table__.columns
            if col.name not in ("instrument_token", "updated_at")
        }
        stmt = stmt.on_conflict_do_update(index_elements=["instrument_token"], set_=update_cols)
        self.session.execute(stmt)
        return len(records)

    def get_by_symbol(self, exchange: str, tradingsymbol: str) -> Instrument | None:
        stmt = select(Instrument).where(
            Instrument.exchange == exchange,
            Instrument.tradingsymbol == tradingsymbol,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def count(self) -> int:
        return self.session.query(Instrument).count()


class OHLCRepository:
    """Read/write access to 1-minute OHLC bars."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_bars(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        stmt = pg_insert(OHLCBar).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["instrument_token", "time"],
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
            },
        )
        self.session.execute(stmt)
        return len(rows)

    def get_range(self, instrument_token: int, start: datetime, end: datetime) -> list[OHLCBar]:
        stmt = (
            select(OHLCBar)
            .where(
                OHLCBar.instrument_token == instrument_token,
                OHLCBar.time >= start,
                OHLCBar.time <= end,
            )
            .order_by(OHLCBar.time)
        )
        return list(self.session.execute(stmt).scalars())
