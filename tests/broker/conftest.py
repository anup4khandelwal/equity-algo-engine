"""Shared test helpers for the broker layer."""

from __future__ import annotations


class FakeClock:
    """A controllable monotonic clock whose `sleep` advances `time`.

    Lets token-bucket tests run deterministically and instantly: instead of
    really sleeping, `sleep(dt)` just moves the virtual clock forward.
    """

    def __init__(self, start: float = 0.0) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds
