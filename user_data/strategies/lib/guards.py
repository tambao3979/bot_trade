"""Fail-closed execution and portfolio-risk guards.

Every helper in this module returns ``False`` when the exchange payload is
missing, malformed, non-finite, or insufficient to establish a safe entry.
That behaviour is deliberate: an unavailable order book is not evidence that
an order is safe to submit.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from numbers import Real
from typing import Any


def _finite_positive(value: Any) -> float | None:
    """Return a finite positive float, otherwise ``None``."""
    if isinstance(value, bool) or not isinstance(value, (Real, str)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def spread_ok(ticker: Mapping[str, Any] | None, max_bps: float = 15.0) -> bool:
    """Check that bid/ask spread is finite and no wider than ``max_bps``."""
    if not isinstance(ticker, Mapping):
        return False
    bid = _finite_positive(ticker.get("bid"))
    ask = _finite_positive(ticker.get("ask"))
    limit = _finite_positive(max_bps)
    if bid is None or ask is None or limit is None or ask < bid:
        return False
    midpoint = (bid + ask) / 2.0
    return math.isfinite(midpoint) and ((ask - bid) / midpoint) * 10_000 <= limit


def slippage_ok(
    orderbook: Mapping[str, Any] | None,
    notional: float,
    max_bps: float = 30.0,
    side: str = "long",
) -> bool:
    """Estimate order-book impact and reject incomplete or expensive fills.

    ``notional`` is denominated in quote currency. Long entries consume asks;
    short entries consume bids. The calculation uses a volume-weighted fill
    price and deliberately rejects an order when the requested notional cannot
    be completely filled from the supplied depth.
    """
    if not isinstance(orderbook, Mapping):
        return False
    requested = _finite_positive(notional)
    limit = _finite_positive(max_bps)
    book_side = "bids" if side.lower() == "short" else "asks"
    levels = orderbook.get(book_side)
    if requested is None or limit is None or not isinstance(levels, Sequence) or not levels:
        return False

    remaining = requested
    filled_cost = 0.0
    filled_amount = 0.0
    best_price: float | None = None
    for level in levels:
        if not isinstance(level, Sequence) or len(level) < 2:
            return False
        price = _finite_positive(level[0])
        amount = _finite_positive(level[1])
        if price is None or amount is None:
            return False
        if best_price is None:
            best_price = price
        level_notional = price * amount
        take_notional = min(remaining, level_notional)
        take_amount = take_notional / price
        filled_cost += take_notional
        filled_amount += take_amount
        remaining -= take_notional
        if remaining <= 1e-9:
            break

    if best_price is None or remaining > 1e-9 or filled_amount <= 0:
        return False
    average_price = filled_cost / filled_amount
    impact = (
        (average_price - best_price) / best_price
        if book_side == "asks"
        else (best_price - average_price) / best_price
    )
    return math.isfinite(impact) and impact * 10_000 <= limit


def liquidity_ok(
    ticker: Mapping[str, Any] | None, min_24h_vol_usd: float = 1_000_000.0
) -> bool:
    """Require finite 24-hour quote volume above the configured minimum."""
    if not isinstance(ticker, Mapping):
        return False
    minimum = _finite_positive(min_24h_vol_usd)
    if minimum is None:
        return False
    volume = _finite_positive(
        ticker.get("quoteVolume", ticker.get("quote_volume", ticker.get("volume")))
    )
    return volume is not None and volume >= minimum


def funding_ok(funding_rate: Real | str | None, max_abs: float = 0.0005) -> bool:
    """Reject non-finite funding or funding whose absolute value is too high."""
    try:
        rate = float(funding_rate)
        limit = float(max_abs)
    except (TypeError, ValueError):
        return False
    return math.isfinite(rate) and math.isfinite(limit) and limit >= 0 and abs(rate) <= limit


def daily_loss_halt(
    equity_start_day: float, equity_now: float, max_pct: float = 2.0
) -> bool:
    """Return whether a daily percentage-loss circuit breaker is active."""
    start = _finite_positive(equity_start_day)
    limit = _finite_positive(max_pct)
    try:
        current = float(equity_now)
    except (TypeError, ValueError):
        return True
    if start is None or limit is None or not math.isfinite(current) or current < 0:
        return True
    return ((start - current) / start) * 100 >= limit
