"""Precise tests for the Indian-equity transaction-cost model."""

from __future__ import annotations

import pytest

from algotrading.backtest.costs import Product, charges_for_fill
from algotrading.strategies.base import Side


def test_intraday_buy_charges_breakdown() -> None:
    c = charges_for_fill(Side.BUY, price=1000.0, quantity=100, product=Product.INTRADAY)
    # turnover = 100_000
    assert c.brokerage == pytest.approx(20.0)  # min(30, 20 cap)
    assert c.stt == pytest.approx(0.0)  # no STT on intraday buy
    assert c.exchange == pytest.approx(2.97)
    assert c.sebi == pytest.approx(0.1)
    assert c.gst == pytest.approx(0.18 * (20 + 2.97 + 0.1))
    assert c.stamp_duty == pytest.approx(3.0)
    assert c.total == pytest.approx(30.2226)


def test_intraday_sell_has_stt_and_no_stamp() -> None:
    c = charges_for_fill(Side.SELL, price=1000.0, quantity=100, product=Product.INTRADAY)
    assert c.stt == pytest.approx(25.0)  # 0.025% of 100_000
    assert c.stamp_duty == pytest.approx(0.0)
    assert c.total == pytest.approx(52.2226)


def test_brokerage_is_capped_at_twenty() -> None:
    # turnover = 1_000_000 -> 0.03% = 300, capped to 20
    c = charges_for_fill(Side.BUY, price=1000.0, quantity=1000, product=Product.INTRADAY)
    assert c.brokerage == pytest.approx(20.0)


def test_delivery_buy_zero_brokerage_full_stt() -> None:
    c = charges_for_fill(Side.BUY, price=1000.0, quantity=100, product=Product.DELIVERY)
    assert c.brokerage == pytest.approx(0.0)
    assert c.stt == pytest.approx(100.0)  # 0.1% of 100_000, both sides
    assert c.stamp_duty == pytest.approx(15.0)  # 0.015% buy
    assert c.total == pytest.approx(118.6226)


def test_costs_scale_with_turnover() -> None:
    small = charges_for_fill(Side.SELL, 100.0, 10, Product.INTRADAY).total
    big = charges_for_fill(Side.SELL, 100.0, 100, Product.INTRADAY).total
    assert big > small
