"""Tests for notifiers."""

from __future__ import annotations

from algotrading.live.notifier import LoggingNotifier, TelegramNotifier


def test_logging_notifier_runs(caplog) -> None:
    with caplog.at_level("INFO", logger="algotrading.notifier"):
        LoggingNotifier().notify("hello")
    assert "hello" in caplog.text


def test_telegram_notifier_uses_injected_sender() -> None:
    sent: list[tuple[str, str, str]] = []
    notifier = TelegramNotifier("tok", "chat", sender=lambda t, c, m: sent.append((t, c, m)))
    notifier.notify("filled")
    assert sent == [("tok", "chat", "filled")]


def test_telegram_notifier_swallows_sender_errors() -> None:
    def boom(*_args):
        raise RuntimeError("network down")

    # Must not raise — notifications can never break trading.
    TelegramNotifier("tok", "chat", sender=boom).notify("filled")
