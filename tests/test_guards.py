"""
Tests for lib/guards.py (T08).
"""

from user_data.strategies.lib.guards import (
    daily_loss_halt,
    funding_ok,
    liquidity_ok,
    slippage_ok,
    spread_ok,
)


def test_spread_ok_threshold():
    assert spread_ok({"bid": 100, "ask": 100.1}, max_bps=15)
    assert not spread_ok({"bid": 100, "ask": 100.5}, max_bps=15)


def test_slippage_ok_under_limit():
    orderbook = {"asks": [(100.0, 10), (100.1, 100)]}
    assert slippage_ok(orderbook, notional=100, max_bps=30)
    # high impact should fail
    assert not slippage_ok(orderbook, notional=1_000_000, max_bps=1)


def test_liquidity_ok():
    assert liquidity_ok({"quoteVolume": 2_000_000}, min_24h_vol_usd=1_000_000)
    assert not liquidity_ok({"quoteVolume": 500_000}, min_24h_vol_usd=1_000_000)


def test_funding_ok():
    assert funding_ok(0.0001, max_abs=0.0005)
    assert not funding_ok(0.001, max_abs=0.0005)


def test_daily_loss_halt():
    assert daily_loss_halt(1000, 970, max_pct=2.0)
    assert not daily_loss_halt(1000, 990, max_pct=2.0)
