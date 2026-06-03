"""Initial schema: instruments, ohlc_bars hypertable, and continuous aggregates.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Higher timeframes derived from the 1-minute base table via continuous
# aggregates: (view name, bucket width in minutes).
_AGGREGATES: list[tuple[str, int]] = [
    ("ohlc_5min", 5),
    ("ohlc_15min", 15),
    ("ohlc_60min", 60),
]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    op.create_table(
        "instruments",
        sa.Column("instrument_token", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("exchange_token", sa.BigInteger(), nullable=True),
        sa.Column("tradingsymbol", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.Column("exchange", sa.String(length=16), nullable=False),
        sa.Column("segment", sa.String(length=32), nullable=True),
        sa.Column("instrument_type", sa.String(length=16), nullable=False),
        sa.Column("lot_size", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("tick_size", sa.Float(), nullable=False, server_default="0.05"),
        sa.Column("expiry", sa.Date(), nullable=True),
        sa.Column("strike", sa.Float(), nullable=True),
        sa.Column("last_price", sa.Float(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_instruments_tradingsymbol", "instruments", ["tradingsymbol"])
    op.create_index("ix_instruments_exchange_symbol", "instruments", ["exchange", "tradingsymbol"])

    op.create_table(
        "ohlc_bars",
        sa.Column(
            "instrument_token",
            sa.BigInteger(),
            sa.ForeignKey("instruments.instrument_token", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("time", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.BigInteger(), nullable=False, server_default="0"),
    )

    # Turn ohlc_bars into a hypertable partitioned on `time`.
    op.execute("SELECT create_hypertable('ohlc_bars', 'time', if_not_exists => TRUE)")

    # Continuous aggregates and their policies cannot run inside a transaction.
    with op.get_context().autocommit_block():
        for view_name, minutes in _AGGREGATES:
            op.execute(
                f"""
                CREATE MATERIALIZED VIEW {view_name}
                WITH (timescaledb.continuous) AS
                SELECT
                    instrument_token,
                    time_bucket('{minutes} minutes', "time") AS bucket,
                    first(open, "time") AS open,
                    max(high) AS high,
                    min(low) AS low,
                    last(close, "time") AS close,
                    sum(volume) AS volume
                FROM ohlc_bars
                GROUP BY instrument_token, bucket
                WITH NO DATA
                """
            )
            op.execute(
                f"""
                SELECT add_continuous_aggregate_policy('{view_name}',
                    start_offset => INTERVAL '3 days',
                    end_offset => INTERVAL '{minutes} minutes',
                    schedule_interval => INTERVAL '{minutes} minutes')
                """
            )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        for view_name, _ in reversed(_AGGREGATES):
            op.execute(f"DROP MATERIALIZED VIEW IF EXISTS {view_name}")

    op.drop_table("ohlc_bars")
    op.drop_index("ix_instruments_exchange_symbol", table_name="instruments")
    op.drop_index("ix_instruments_tradingsymbol", table_name="instruments")
    op.drop_table("instruments")
