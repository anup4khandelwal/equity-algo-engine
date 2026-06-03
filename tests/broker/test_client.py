"""Tests for the rate-limited Kite client wrapper.

The underlying Kite SDK is fully mocked — no network access.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from algotrading.broker.client import KiteClient
from algotrading.broker.throttle import RateCategory
from algotrading.broker.token_store import KiteToken, TokenStore


class RecordingLimiter:
    """Stand-in RateLimiter that records categories instead of throttling."""

    def __init__(self) -> None:
        self.calls: list[RateCategory] = []

    def acquire(self, category: RateCategory, tokens: float = 1.0) -> None:
        self.calls.append(category)


@pytest.fixture
def kite() -> MagicMock:
    return MagicMock(name="KiteConnect")


@pytest.fixture
def limiter() -> RecordingLimiter:
    return RecordingLimiter()


def test_methods_delegate_to_underlying_kite(kite: MagicMock, limiter: RecordingLimiter) -> None:
    client = KiteClient(kite, rate_limiter=limiter)
    kite.profile.return_value = {"user_id": "AB1234"}

    assert client.profile() == {"user_id": "AB1234"}
    kite.profile.assert_called_once_with()


def test_calls_are_routed_to_correct_rate_category(
    kite: MagicMock, limiter: RecordingLimiter
) -> None:
    client = KiteClient(kite, rate_limiter=limiter)

    client.profile()
    client.ltp(["NSE:INFY"])
    client.historical_data(123, "2026-01-01", "2026-01-02", "day")
    client.place_order(variety="regular", tradingsymbol="INFY")

    assert limiter.calls == [
        RateCategory.general,
        RateCategory.quote,
        RateCategory.historical,
        RateCategory.order,
    ]


def test_throttle_runs_before_the_call(kite: MagicMock) -> None:
    order: list[str] = []
    limiter = MagicMock()
    limiter.acquire.side_effect = lambda *a, **k: order.append("acquire")
    kite.profile.side_effect = lambda *a, **k: order.append("call")

    KiteClient(kite, rate_limiter=limiter).profile()
    assert order == ["acquire", "call"]


def test_historical_data_passes_through_kwargs(kite: MagicMock, limiter: RecordingLimiter) -> None:
    client = KiteClient(kite, rate_limiter=limiter)
    client.historical_data(99, "2026-01-01", "2026-01-02", "5minute", continuous=True, oi=True)
    kite.historical_data.assert_called_once_with(
        99, "2026-01-01", "2026-01-02", "5minute", continuous=True, oi=True
    )


def test_from_settings_prefers_stored_token(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    fake_kite = MagicMock(name="KiteConnect")
    kite_ctor = MagicMock(return_value=fake_kite)
    monkeypatch.setattr("kiteconnect.KiteConnect", kite_ctor, raising=False)

    store = TokenStore(tmp_path / "kite_token.json")
    store.save(KiteToken(access_token="stored-token"))

    settings = MagicMock()
    settings.kite_api_key = "api-key"
    settings.kite_access_token = "settings-token"

    KiteClient.from_settings(settings, token_store=store)

    kite_ctor.assert_called_once_with(api_key="api-key")
    fake_kite.set_access_token.assert_called_once_with("stored-token")


def test_from_settings_falls_back_to_settings_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    fake_kite = MagicMock(name="KiteConnect")
    monkeypatch.setattr(
        "kiteconnect.KiteConnect",
        MagicMock(return_value=fake_kite),
        raising=False,
    )

    store = TokenStore(tmp_path / "absent.json")  # no stored token
    settings = MagicMock()
    settings.kite_api_key = "api-key"
    settings.kite_access_token = "settings-token"

    KiteClient.from_settings(settings, token_store=store)
    fake_kite.set_access_token.assert_called_once_with("settings-token")


def test_from_settings_without_any_token_does_not_set_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    fake_kite = MagicMock(name="KiteConnect")
    monkeypatch.setattr(
        "kiteconnect.KiteConnect",
        MagicMock(return_value=fake_kite),
        raising=False,
    )
    store = TokenStore(tmp_path / "absent.json")
    settings = MagicMock()
    settings.kite_api_key = "api-key"
    settings.kite_access_token = None

    KiteClient.from_settings(settings, token_store=store)
    fake_kite.set_access_token.assert_not_called()
