"""Application configuration, loaded from the environment / `.env`.

All secrets and connection strings are read here via pydantic-settings. Nothing
is ever hardcoded, and nothing in this module should print or log a secret.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(StrEnum):
    """Execution mode. The system defaults to ``paper`` and only ever touches
    real order endpoints in ``live`` mode (which stays stubbed for now)."""

    paper = "paper"
    live = "live"


class Settings(BaseSettings):
    """Typed application settings.

    Field names map case-insensitively to environment variables, e.g.
    ``kite_api_key`` reads ``KITE_API_KEY``. See ``.env.example`` for the full
    list of supported variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Zerodha Kite Connect ------------------------------------------------
    kite_api_key: str = Field(description="Kite Connect app API key.")
    kite_api_secret: str = Field(description="Kite Connect app API secret.")
    kite_access_token: str | None = Field(
        default=None,
        description="Daily access token (expires every morning). Managed by "
        "scripts/refresh_token.py and never committed.",
    )

    # --- Storage -------------------------------------------------------------
    database_url: str = Field(description="SQLAlchemy URL for the TimescaleDB/Postgres instance.")
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis URL for positions, signal cache, and throttle buckets.",
    )

    # --- Engine --------------------------------------------------------------
    trading_mode: TradingMode = Field(
        default=TradingMode.paper,
        description="paper (default) or live. Live order execution is out of scope and stubbed.",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance.

    Using a function (rather than a module-level singleton) keeps importing this
    module side-effect free, so it can be imported without a populated `.env`.
    """

    return Settings()
