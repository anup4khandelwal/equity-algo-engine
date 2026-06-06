"""Tests for the engine-level RiskManager."""

from __future__ import annotations

from datetime import time

from algotrading.risk.manager import RiskLimits, RiskManager


def _mgr(**kw) -> RiskManager:
    return RiskManager(RiskLimits(**kw))


def test_allows_entry_within_limits() -> None:
    mgr = _mgr(max_open_positions=3, daily_loss_limit=5000)
    assert mgr.can_enter(now=time(10, 0), open_positions=1, day_pnl=-100.0)


def test_blocks_when_max_positions_reached() -> None:
    mgr = _mgr(max_open_positions=2)
    assert not mgr.can_enter(now=time(10, 0), open_positions=2, day_pnl=0.0)


def test_kill_switch_latches_on_daily_loss() -> None:
    mgr = _mgr(daily_loss_limit=5000)
    assert not mgr.can_enter(now=time(10, 0), open_positions=0, day_pnl=-5000.0)
    assert mgr.halted
    # Even after a recovery, it stays halted until reset.
    assert not mgr.can_enter(now=time(10, 0), open_positions=0, day_pnl=1000.0)


def test_reset_day_clears_kill_switch() -> None:
    mgr = _mgr(daily_loss_limit=5000)
    mgr.update_pnl(-6000.0)
    assert mgr.halted
    mgr.reset_day()
    assert not mgr.halted
    assert mgr.can_enter(now=time(10, 0), open_positions=0, day_pnl=0.0)


def test_no_new_trades_after_cutoff() -> None:
    mgr = _mgr(no_new_trades_after=time(15, 0))
    assert not mgr.can_enter(now=time(15, 0), open_positions=0, day_pnl=0.0)
    assert not mgr.can_enter(now=time(15, 10), open_positions=0, day_pnl=0.0)


def test_should_square_off_at_time() -> None:
    mgr = _mgr(square_off_at=time(15, 15))
    assert not mgr.should_square_off(time(15, 14))
    assert mgr.should_square_off(time(15, 15))
    assert mgr.should_square_off(time(15, 20))
