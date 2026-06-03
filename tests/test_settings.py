"""Phase 0 smoke tests for configuration loading."""

from __future__ import annotations

import pytest
from config.settings import Settings, TradingMode, get_settings


@pytest.fixture
def _kite_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provide the minimal required environment for Settings to validate."""
    monkeypatch.setenv("KITE_API_KEY", "test-key")
    monkeypatch.setenv("KITE_API_SECRET", "test-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://algo:algo@localhost:5432/algo_test")
    # Ensure the cached getter re-reads the patched environment.
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_defaults_paper_mode(_kite_env: None) -> None:
    settings = Settings()
    assert settings.trading_mode is TradingMode.paper
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.kite_access_token is None


def test_get_settings_is_cached(_kite_env: None) -> None:
    assert get_settings() is get_settings()


def test_trading_mode_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KITE_API_KEY", "k")
    monkeypatch.setenv("KITE_API_SECRET", "s")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://a:b@localhost:5432/c")
    monkeypatch.setenv("TRADING_MODE", "paper")
    assert Settings().trading_mode is TradingMode.paper
