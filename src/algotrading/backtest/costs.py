"""Realistic Indian-equity transaction costs.

Every backtest must report **net** P&L, so each simulated fill is charged the
full stack of statutory and broker costs. Defaults below follow Zerodha's
published equity rates (NSE). Rates are configurable in one place so they are
easy to audit and update; nothing here is a hidden magic number.

References (Zerodha brokerage/charges, equity segment):
- Brokerage: intraday min(0.03% of turnover, ₹20) per order; ₹0 for delivery.
- STT/CTT:   intraday 0.025% on the SELL turnover; delivery 0.1% on both sides.
- Exchange:  NSE 0.00297% of turnover.
- SEBI:      ₹10 per crore = 0.0001% of turnover.
- GST:       18% on (brokerage + exchange + SEBI).
- Stamp duty: on the BUY side only — intraday 0.003%, delivery 0.015%.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from algotrading.strategies.base import Side


class Product(StrEnum):
    """Zerodha product type. Intraday (MIS) vs delivery (CNC)."""

    INTRADAY = "intraday"
    DELIVERY = "delivery"


@dataclass(frozen=True)
class CostConfig:
    """Cost rates as fractions of turnover (unless noted)."""

    brokerage_intraday_rate: float = 0.0003  # 0.03%
    brokerage_intraday_cap: float = 20.0  # ₹ per order
    brokerage_delivery_rate: float = 0.0  # ₹0 for equity delivery
    stt_intraday_sell: float = 0.00025  # 0.025% on sell turnover
    stt_delivery: float = 0.001  # 0.1% on both sides
    exchange_txn_rate: float = 0.0000297  # NSE 0.00297%
    sebi_rate: float = 0.000001  # ₹10 / crore
    gst_rate: float = 0.18  # 18% on brokerage + exchange + sebi
    stamp_intraday_buy: float = 0.00003  # 0.003% on buy turnover
    stamp_delivery_buy: float = 0.00015  # 0.015% on buy turnover


@dataclass(frozen=True)
class Charges:
    """Itemised charges for a single fill."""

    brokerage: float
    stt: float
    exchange: float
    sebi: float
    gst: float
    stamp_duty: float

    @property
    def total(self) -> float:
        return self.brokerage + self.stt + self.exchange + self.sebi + self.gst + self.stamp_duty


def charges_for_fill(
    side: Side,
    price: float,
    quantity: int,
    product: Product = Product.INTRADAY,
    config: CostConfig | None = None,
) -> Charges:
    """Compute the full charge breakdown for one executed fill."""
    cfg = config or CostConfig()
    turnover = price * quantity
    is_buy = side is Side.BUY

    if product is Product.INTRADAY:
        brokerage = min(cfg.brokerage_intraday_rate * turnover, cfg.brokerage_intraday_cap)
        stt = 0.0 if is_buy else cfg.stt_intraday_sell * turnover
        stamp = cfg.stamp_intraday_buy * turnover if is_buy else 0.0
    else:
        brokerage = cfg.brokerage_delivery_rate * turnover
        stt = cfg.stt_delivery * turnover
        stamp = cfg.stamp_delivery_buy * turnover if is_buy else 0.0

    exchange = cfg.exchange_txn_rate * turnover
    sebi = cfg.sebi_rate * turnover
    gst = cfg.gst_rate * (brokerage + exchange + sebi)

    return Charges(
        brokerage=brokerage,
        stt=stt,
        exchange=exchange,
        sebi=sebi,
        gst=gst,
        stamp_duty=stamp,
    )
