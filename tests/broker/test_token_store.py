"""Tests for local access-token persistence."""

from __future__ import annotations

import stat
from pathlib import Path

from algotrading.broker.token_store import KiteToken, TokenStore


def test_save_then_load_round_trip(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "secrets" / "kite_token.json")
    token = KiteToken(
        access_token="secret-token",
        public_token="pub",
        user_id="AB1234",
        login_time="2026-06-03T09:15:00",
    )
    store.save(token)

    loaded = store.load()
    assert loaded == token


def test_load_returns_none_when_absent(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "missing.json")
    assert store.load() is None


def test_load_returns_none_without_access_token(tmp_path: Path) -> None:
    path = tmp_path / "kite_token.json"
    path.write_text('{"public_token": "pub"}', encoding="utf-8")
    assert TokenStore(path).load() is None


def test_saved_file_is_owner_only(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "kite_token.json")
    store.save(KiteToken(access_token="x"))
    mode = stat.S_IMODE(store.path.stat().st_mode)
    assert mode == 0o600
