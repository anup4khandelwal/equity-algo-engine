"""Add the fills table (persisted execution log).

Revision ID: 0002_fills
Revises: 0001_initial
Create Date: 2026-06-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_fills"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fills",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("instrument_token", sa.BigInteger(), nullable=False),
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("charges", sa.Float(), nullable=False, server_default="0"),
        sa.Column("strategy", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("reason", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("product", sa.String(length=16), nullable=False, server_default="intraday"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="FILLED"),
    )
    op.create_index("ix_fills_time", "fills", ["time"])
    op.create_index("ix_fills_instrument_token", "fills", ["instrument_token"])
    op.create_index("ix_fills_strategy", "fills", ["strategy"])


def downgrade() -> None:
    op.drop_index("ix_fills_strategy", table_name="fills")
    op.drop_index("ix_fills_instrument_token", table_name="fills")
    op.drop_index("ix_fills_time", table_name="fills")
    op.drop_table("fills")
