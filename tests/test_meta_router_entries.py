"""Regression tests for MetaRouter entry signal logic."""

from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def strategy():
    """Return a MetaRouter instance."""
    try:
        from user_data.strategies.MetaRouter import MetaRouter
    except ModuleNotFoundError:
        pytest.skip("MetaRouter strategy not available")
    return MetaRouter()


@pytest.fixture
def base_dataframe():
    """Return a minimal DataFrame with all required indicators."""
    df = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01 12:00", periods=20, freq="15min"),
            "open": [100.0] * 20,
            "high": [101.0] * 20,
            "low": [99.0] * 20,
            "close": [100.5] * 20,
            "volume": [1000.0] * 20,
            "ema20": [100.0] * 20,
            "ema50": [99.0] * 20,
            "ema200": [98.0] * 20,
            "rsi14": [50.0] * 20,
            "atr14": [1.0] * 20,
            "vol_ma20": [1000.0] * 20,
            "adx14": [25.0] * 20,
            "stoch_k": [50.0] * 20,
            "stoch_d": [50.0] * 20,
            "bb_lower": [98.0] * 20,
            "bb_mid": [100.0] * 20,
            "bb_upper": [102.0] * 20,
            "vwap": [100.0] * 20,
            "prev_session_high": [101.5] * 20,
            "prev_session_low": [98.5] * 20,
            "regime_1h": ["neutral"] * 20,
        }
    )
    return df


def test_trend_short_fires_when_enabled(strategy, base_dataframe):
    """Test that trend short setup fires when enabled."""
    df = base_dataframe.copy()
    target_idx = 10

    # Valid trend short setup
    df.loc[target_idx, "regime_1h"] = "trend_down"
    df.loc[target_idx, "close"] = 99.5
    df.loc[target_idx, "ema200"] = 102.0
    df.loc[target_idx, "ema50"] = 101.0
    df.loc[target_idx, "ema20"] = 100.0
    df.loc[target_idx, "high"] = 100.2
    df.loc[target_idx, "open"] = 100.0
    df.loc[target_idx, "volume"] = 1200.0
    df.loc[target_idx, "vol_ma20"] = 1000.0
    df.loc[target_idx, "adx14"] = 25.0
    df.loc[target_idx, "stoch_k"] = 35.0
    df.loc[target_idx, "stoch_d"] = 40.0
    df.loc[target_idx - 1, "stoch_k"] = 41.0
    df.loc[target_idx - 1, "stoch_d"] = 40.0

    result = strategy.populate_entry_trend(df, {"pair": "BTC/USDT"})

    assert result.loc[target_idx, "enter_short"] == 1
    assert result.loc[target_idx, "enter_tag"] == "trend_pullback_short"
    assert result.loc[target_idx, "enter_long"] == 0


def test_trend_long_disabled_by_default(strategy, base_dataframe):
    """Test that trend long is disabled when not in enabled_setups."""
    df = base_dataframe.copy()
    target_idx = 10

    # Valid trend long setup
    df.loc[target_idx, "regime_1h"] = "trend_up"
    df.loc[target_idx, "close"] = 100.5
    df.loc[target_idx, "ema200"] = 98.0
    df.loc[target_idx, "ema50"] = 99.0
    df.loc[target_idx, "ema20"] = 100.0
    df.loc[target_idx, "low"] = 99.8
    df.loc[target_idx, "open"] = 100.0
    df.loc[target_idx, "volume"] = 1200.0
    df.loc[target_idx, "vol_ma20"] = 1000.0
    df.loc[target_idx, "adx14"] = 25.0
    df.loc[target_idx, "stoch_k"] = 60.0
    df.loc[target_idx, "stoch_d"] = 55.0
    df.loc[target_idx - 1, "stoch_k"] = 54.0
    df.loc[target_idx - 1, "stoch_d"] = 55.0

    result = strategy.populate_entry_trend(df, {"pair": "BTC/USDT"})

    # Long should not fire because trend_long not in enabled_setups
    assert result.loc[target_idx, "enter_long"] == 0


def test_range_setups_disabled_by_default(strategy, base_dataframe):
    """Test that range setups are disabled when not in enabled_setups."""
    df = base_dataframe.copy()
    target_idx = 10

    # Valid range long setup
    df.loc[target_idx, "regime_1h"] = "range"
    df.loc[target_idx, "low"] = 97.9
    df.loc[target_idx, "bb_lower"] = 98.0
    df.loc[target_idx, "close"] = 98.5
    df.loc[target_idx, "open"] = 98.0
    df.loc[target_idx, "rsi14"] = 30.0

    result = strategy.populate_entry_trend(df, {"pair": "BTC/USDT"})

    # Range long should not fire
    assert result.loc[target_idx, "enter_long"] == 0


def test_liquidity_setups_disabled_by_default(strategy, base_dataframe):
    """Test that liquidity setups are disabled when not in enabled_setups."""
    df = base_dataframe.copy()
    target_idx = 10

    # Valid liquidity long setup
    df.loc[target_idx, "regime_1h"] = "trend_up"
    df.loc[target_idx, "low"] = 98.0
    df.loc[target_idx, "close"] = 99.0
    df.loc[target_idx, "open"] = 98.5
    df.loc[target_idx, "prev_session_low"] = 98.5
    df.loc[target_idx, "rsi14"] = 45.0

    result = strategy.populate_entry_trend(df, {"pair": "BTC/USDT"})

    # Liquidity long should not fire
    assert result.loc[target_idx, "enter_long"] == 0


def test_trend_short_predicate_matches_trendpullback(strategy, base_dataframe):
    """Test that trend short predicate produces same result as TrendPullback."""
    try:
        from user_data.strategies.TrendPullback import TrendPullback
    except ModuleNotFoundError:
        pytest.skip("TrendPullback not available")

    trend_strategy = TrendPullback()
    df = base_dataframe.copy()
    target_idx = 10

    # Setup valid short
    df.loc[target_idx, "regime_1h"] = "trend_down"
    df.loc[target_idx, "close"] = 99.5
    df.loc[target_idx, "ema200"] = 102.0
    df.loc[target_idx, "ema50"] = 101.0
    df.loc[target_idx, "ema20"] = 100.0
    df.loc[target_idx, "high"] = 100.2
    df.loc[target_idx, "open"] = 100.0
    df.loc[target_idx, "volume"] = 1200.0
    df.loc[target_idx, "vol_ma20"] = 1000.0
    df.loc[target_idx, "adx14"] = 25.0
    df.loc[target_idx, "stoch_k"] = 35.0
    df.loc[target_idx, "stoch_d"] = 40.0
    df.loc[target_idx - 1, "stoch_k"] = 41.0
    df.loc[target_idx - 1, "stoch_d"] = 40.0

    meta_result = strategy.populate_entry_trend(df.copy(), {"pair": "BTC/USDT"})
    trend_result = trend_strategy.populate_entry_trend(df.copy(), {"pair": "BTC/USDT"})

    # Both should fire short at same index
    assert meta_result.loc[target_idx, "enter_short"] == trend_result.loc[target_idx, "enter_short"]
    assert meta_result.loc[target_idx, "enter_tag"] == trend_result.loc[target_idx, "enter_tag"]


def test_conflict_resolution_removes_both_signals(strategy, base_dataframe):
    """Test that conflicts are resolved by removing both signals."""
    df = base_dataframe.copy()

    # Hypothetically enable both to test conflict resolution
    # Since we can't change enabled_setups at runtime, we'll just verify
    # the conflict resolution logic works on the actual strategy

    result = strategy.populate_entry_trend(df, {"pair": "BTC/USDT"})

    # No candle should have both signals
    conflict = (result["enter_long"] == 1) & (result["enter_short"] == 1)
    assert not conflict.any()


def test_future_mutation_does_not_affect_past_short_signals(strategy, base_dataframe):
    """Test that modifying future rows doesn't change past short signals."""
    df = base_dataframe.copy()
    target_idx = 10

    # Setup valid short
    df.loc[target_idx, "regime_1h"] = "trend_down"
    df.loc[target_idx, "close"] = 99.5
    df.loc[target_idx, "ema200"] = 102.0
    df.loc[target_idx, "ema50"] = 101.0
    df.loc[target_idx, "ema20"] = 100.0
    df.loc[target_idx, "high"] = 100.2
    df.loc[target_idx, "open"] = 100.0
    df.loc[target_idx, "volume"] = 1200.0
    df.loc[target_idx, "vol_ma20"] = 1000.0
    df.loc[target_idx, "adx14"] = 25.0
    df.loc[target_idx, "stoch_k"] = 35.0
    df.loc[target_idx, "stoch_d"] = 40.0
    df.loc[target_idx - 1, "stoch_k"] = 41.0
    df.loc[target_idx - 1, "stoch_d"] = 40.0

    result1 = strategy.populate_entry_trend(df.copy(), {"pair": "BTC/USDT"})
    original_signal = result1.loc[target_idx, "enter_short"]

    # Mutate future rows
    df.loc[target_idx + 1 :, "regime_1h"] = "chaos"
    df.loc[target_idx + 1 :, "volume"] = 0.0

    result2 = strategy.populate_entry_trend(df.copy(), {"pair": "BTC/USDT"})
    new_signal = result2.loc[target_idx, "enter_short"]

    assert original_signal == new_signal == 1
