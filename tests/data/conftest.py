"""Fixtures for DB-integration tests.

These tests require a reachable PostgreSQL/TimescaleDB (provided by CI via the
``DATABASE_URL`` env var). When no database is available — e.g. a quick local
unit run — they skip cleanly rather than fail.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from algotrading.data.models import Base


@pytest.fixture(scope="session")
def db_engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set; skipping DB integration tests")

    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"database not reachable ({exc!r}); skipping DB integration tests")

    # Idempotent: tables already exist after `alembic upgrade head` in CI.
    Base.metadata.create_all(engine, checkfirst=True)
    return engine


@pytest.fixture
def db_session(db_engine):
    """A session wrapped in a transaction that is rolled back after each test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
