"""Notifications for fills and errors.

A tiny pluggable interface. The default logs; an optional Telegram backend
posts via the Bot API. The HTTP sender is injectable so it is testable without
network access.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Protocol

logger = logging.getLogger("algotrading.notifier")


class Notifier(Protocol):
    def notify(self, message: str) -> None: ...


class LoggingNotifier:
    """Default notifier: writes to the application log."""

    def notify(self, message: str) -> None:
        logger.info(message)


def _http_send(token: str, chat_id: str, message: str) -> None:  # pragma: no cover - network
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode()
    with urllib.request.urlopen(url, data=data, timeout=10) as resp:  # noqa: S310
        json.loads(resp.read().decode())


class TelegramNotifier:
    """Posts messages to a Telegram chat via the Bot API.

    ``sender`` defaults to a urllib-based HTTP call but is injectable for tests.
    """

    def __init__(self, token: str, chat_id: str, sender=_http_send) -> None:
        self._token = token
        self._chat_id = chat_id
        self._send = sender

    def notify(self, message: str) -> None:
        try:
            self._send(self._token, self._chat_id, message)
        except Exception:  # pragma: no cover - never let notifications break trading
            logger.exception("Failed to send Telegram notification")
