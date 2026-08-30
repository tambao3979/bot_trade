"""Regression coverage for fail-closed execution and no-lookahead controls."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
from freqtrade.enums import RunMode

import user_data.strategies.base.BaseRiskStrategy as risk_module
from user_data.strategies.base.BaseRiskStrategy import BaseRiskStrategy
from user_data.strategies.lib.guards import daily_loss_halt, slippage_ok, spread_ok
from user_data.strategies.lib.indicators import adx, atr_pct, vwap_session
from user_data.strategies.MetaRouter import MetaRouter


def _candles(rows: int = 30) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=rows, freq="15min", tz="UTC"),
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 1_000.0,
        }
    )


def _strategy() -> BaseRiskStrategy:
    strategy = BaseRiskStrategy({})
    strategy.dp = MagicMock()
    strategy.dp.get_analyzed_dataframe.return_value = (_candles(), None)
    strategy.wallets = MagicMock()
    strategy.wallets.get_total_stake_amount.return_value = 1_000.0
    return strategy


def test_position_size_uses_closed_atr_and_never_open_candle() -> None:
    strategy = _strategy()
    frame = _candles()
    frame["atr14"] = 2.0
    frame.loc[frame.index[-1], "atr14"] = np.nan  # current candle is unusable
    strategy.dp.get_analyzed_dataframe.return_value = (frame, None)

    stake = strategy.custom_stake_amount(
        pair="BTC/USDC:USDC",
        current_time=datetime.now(UTC),
        current_rate=100.0,
        proposed_stake=20.0,
        min_stake=10.0,
        max_stake=200.0,
        leverage=1.0,
        entry_tag=None,
        side="long",
    )

    assert stake == 200.0


def test_position_size_rejects_when_its_required_live_state_is_unavailable() -> None:
    strategy = BaseRiskStrategy({})

    stake = strategy.custom_stake_amount(
        pair="BTC/USDC:USDC",
        current_time=datetime.now(UTC),
        current_rate=100.0,
        proposed_stake=20.0,
        min_stake=10.0,
        max_stake=200.0,
        leverage=1.0,
        entry_tag=None,
        side="long",
    )

    assert stake == 0.0


def test_position_size_caps_position_notional_before_leverage_conversion() -> None:
    strategy = _strategy()
    frame = _candles()
    frame["atr14"] = 0.1
    strategy.dp.get_analyzed_dataframe.return_value = (frame, None)

    stake = strategy.custom_stake_amount(
        pair="BTC/USDC:USDC",
        current_time=datetime.now(UTC),
        current_rate=100.0,
        proposed_stake=20.0,
        min_stake=10.0,
        max_stake=200.0,
        leverage=2.0,
        entry_tag=None,
        side="long",
    )

    assert stake == 125.0


def test_circuit_breaker_halts_daily_loss_and_peak_drawdown() -> None:
    import tempfile
    from pathlib import Path
    from user_data.strategies.lib.risk_state import RiskStateManager

    # Test with temporary risk state file
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "risk_state.json"

        # Test 1: Drawdown from peak triggers halt
        strategy = _strategy()
        strategy._risk_manager = RiskStateManager(state_file)
        strategy.wallets.get_total_stake_amount.return_value = 1_000.0
        now = datetime(2024, 1, 1, tzinfo=UTC)

        # Initialize peak
        assert not strategy.circuit_breaker_active(now)

        # Drop below max drawdown threshold (10%)
        strategy.wallets.get_total_stake_amount.return_value = 850.0
        assert strategy.circuit_breaker_active(now)

    # Test 2: Daily loss triggers halt
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "risk_state.json"

        strategy = _strategy()
        strategy._risk_manager = RiskStateManager(state_file)
        strategy.wallets.get_total_stake_amount.return_value = 1_000.0

        # Initialize daily start equity
        strategy.circuit_breaker_active(now)

        # Record loss exceeding daily limit (2%)
        strategy._risk_manager.record_trade_pnl(-25.0, now)  # -2.5% loss
        assert strategy.circuit_breaker_active(now)


def test_entry_guard_requires_complete_market_data() -> None:
    strategy = _strategy()

    # Populate cache with valid snapshot (tight spread, sufficient liquidity, funding rate)
    strategy._snapshot_cache.update(
        "BTC/USDC:USDC",
        ticker={"bid": 100.0, "ask": 100.1, "quoteVolume": 2_000_000, "fundingRate": 0.0001},
        orderbook={
            "asks": [[100.1, 100.0]],
            "bids": [[100.0, 100.0]],
        },
    )

    assert strategy.confirm_trade_entry(
        "BTC/USDC:USDC",
        "limit",
        1.0,
        100.0,
        "GTC",
        datetime.now(UTC),
        None,
        "long",
    )

    # Update cache with wide spread - should reject
    strategy._snapshot_cache.update(
        "BTC/USDC:USDC",
        ticker={"bid": 100.0, "ask": 101.0, "quoteVolume": 2_000_000, "fundingRate": 0.0001},
        orderbook={
            "asks": [[101.0, 100.0]],
            "bids": [[100.0, 100.0]],
        },
    )

    assert not strategy.confirm_trade_entry(
        "BTC/USDC:USDC",
        "limit",
        1.0,
        100.0,
        "GTC",
        datetime.now(UTC),
        None,
        "long",
    )


def test_entry_guard_is_bypassed_only_for_historical_engines() -> None:
    strategy = BaseRiskStrategy({"runmode": RunMode.BACKTEST})
    assert strategy.confirm_trade_entry(
        "BTC/USDC:USDC",
        "market",
        1.0,
        100.0,
        "GTC",
        datetime.now(UTC),
        None,
        "long",
    )


def test_guards_fail_closed_and_use_bid_book_for_shorts() -> None:
    assert not spread_ok({"bid": 0.0, "ask": 1.0})
    assert daily_loss_halt(0.0, 1_000.0)
    assert slippage_ok({"bids": [(100.0, 10.0)]}, 100.0, side="short")
    assert not slippage_ok({"asks": [(100.0, 10.0)]}, 100.0, side="short")


def test_indicators_never_emit_infinite_values() -> None:
    frame = _candles()
    frame.loc[frame.index[5], "close"] = 0.0
    frame["volume"] = 0.0
    for series in (atr_pct(frame), vwap_session(frame), adx(frame)):
        assert not np.isinf(series.to_numpy(dtype=float, na_value=np.nan)).any()


def test_informative_regime_waits_for_the_hour_to_close(monkeypatch) -> None:
    strategy = _strategy()
    base = _candles(5)
    informative = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-01T00:00:00Z")],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.0],
            "volume": [100.0],
        }
    )
    strategy.dp.get_pair_dataframe.return_value = informative
    monkeypatch.setattr(
        risk_module,
        "classify_regime",
        lambda frame: pd.Series(["trend_up"], index=frame.index),
    )

    result = strategy.informative_regime(base)

    assert result.iloc[:4].eq("range").all()
    assert result.iloc[4] == "trend_up"


def test_strategy_populates_without_an_injected_data_provider() -> None:
    strategy = MetaRouter({})
    frame = _candles(250)
    result = strategy.populate_indicators(frame, {"pair": "BTC/USDC:USDC"})
    assert result["regime_1h"].eq("range").all()


def test_strategy_source_has_no_negative_shift_or_centered_window() -> None:
    strategy_root = Path("user_data/strategies")
    for source in strategy_root.rglob("*.py"):
        text = source.read_text(encoding="utf-8")
        assert "shift(-" not in text, source
        assert "center=True" not in text, source
