"""Regression tests for TrendPullback entry signal logic."""

from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def strategy():
    """Return a TrendPullback instance with default parameters."""
    try:
        from user_data.strategies.TrendPullback import TrendPullback
    except ModuleNotFoundError:
        pytest.skip("TrendPullback strategy not available")
    return TrendPullback()


@pytest.fixture
def base_dataframe():
    """Return a minimal DataFrame with all required indicators."""
    df = pd.DataFrame(
        {
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
            "regime_1h": ["neutral"] * 20,
        }
    )
    return df


def test_valid_long_entry_fires_with_correct_tag(strategy, base_dataframe):
    """Test that a valid long setup fires with trend_pullback_long tag."""
    df = base_dataframe.copy()
    target_idx = 10

    # Setup valid long conditions at target_idx
    df.loc[target_idx, "regime_1h"] = "trend_up"
    df.loc[target_idx, "close"] = 100.5
    df.loc[target_idx, "ema200"] = 98.0
    df.loc[target_idx, "ema50"] = 99.0
    df.loc[target_idx, "ema20"] = 100.0
    df.loc[target_idx, "low"] = 99.8  # Touched EMA20 * 1.003
    df.loc[target_idx, "open"] = 100.0
    df.loc[target_idx, "volume"] = 1200.0
    df.loc[target_idx, "vol_ma20"] = 1000.0
    df.loc[target_idx, "adx14"] = 25.0
    df.loc[target_idx, "stoch_k"] = 60.0
    df.loc[target_idx, "stoch_d"] = 55.0
    df.loc[target_idx - 1, "stoch_k"] = 54.0
    df.loc[target_idx - 1, "stoch_d"] = 55.0

    result = strategy.populate_entry_trend(df, {"pair": "BTC/USDT"})

    assert result.loc[target_idx, "enter_long"] == 1
    assert result.loc[target_idx, "enter_tag"] == "trend_pullback_long"
    assert result.loc[target_idx, "enter_short"] == 0


def test_valid_short_entry_fires_with_correct_tag(strategy, base_dataframe):
    """Test that a valid short setup fires with trend_pullback_short tag."""
    df = base_dataframe.copy()
    target_idx = 10

    # Setup valid short conditions
    df.loc[target_idx, "regime_1h"] = "trend_down"
    df.loc[target_idx, "close"] = 99.5
    df.loc[target_idx, "ema200"] = 102.0
    df.loc[target_idx, "ema50"] = 101.0
    df.loc[target_idx, "ema20"] = 100.0
    df.loc[target_idx, "high"] = 100.2  # Touched EMA20 * 0.997
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


def test_missing_regime_prevents_long_entry(strategy, base_dataframe):
    """Test that missing trend_up regime prevents long entry."""
    df = base_dataframe.copy()
    target_idx = 10

    # Valid conditions except regime
    df.loc[target_idx, "regime_1h"] = "neutral"
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

    assert result.loc[target_idx, "enter_long"] == 0


def test_missing_ema_alignment_prevents_entry(strategy, base_dataframe):
    """Test that broken EMA alignment prevents entry."""
    df = base_dataframe.copy()
    target_idx = 10

    # Valid conditions except EMA alignment
    df.loc[target_idx, "regime_1h"] = "trend_up"
    df.loc[target_idx, "close"] = 100.5
    df.loc[target_idx, "ema200"] = 98.0
    df.loc[target_idx, "ema50"] = 101.0  # Wrong order
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

    assert result.loc[target_idx, "enter_long"] == 0


def test_missing_bullish_candle_prevents_long_entry(strategy, base_dataframe):
    """Test that bearish candle prevents long entry."""
    df = base_dataframe.copy()
    target_idx = 10

    # Valid conditions except candle is bearish
    df.loc[target_idx, "regime_1h"] = "trend_up"
    df.loc[target_idx, "close"] = 99.5  # Below open
    df.loc[target_idx, "open"] = 100.0
    df.loc[target_idx, "ema200"] = 98.0
    df.loc[target_idx, "ema50"] = 99.0
    df.loc[target_idx, "ema20"] = 100.0
    df.loc[target_idx, "low"] = 99.8
    df.loc[target_idx, "volume"] = 1200.0
    df.loc[target_idx, "vol_ma20"] = 1000.0
    df.loc[target_idx, "adx14"] = 25.0
    df.loc[target_idx, "stoch_k"] = 60.0
    df.loc[target_idx, "stoch_d"] = 55.0
    df.loc[target_idx - 1, "stoch_k"] = 54.0
    df.loc[target_idx - 1, "stoch_d"] = 55.0

    result = strategy.populate_entry_trend(df, {"pair": "BTC/USDT"})

    assert result.loc[target_idx, "enter_long"] == 0


def test_missing_cross_prevents_entry(strategy, base_dataframe):
    """Test that missing stochastic cross prevents entry."""
    df = base_dataframe.copy()
    target_idx = 10

    # Valid conditions except no cross
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
    df.loc[target_idx - 1, "stoch_k"] = 61.0  # Already above
    df.loc[target_idx - 1, "stoch_d"] = 55.0

    result = strategy.populate_entry_trend(df, {"pair": "BTC/USDT"})

    assert result.loc[target_idx, "enter_long"] == 0


def test_low_adx_prevents_entry(strategy, base_dataframe):
    """Test that low ADX prevents entry."""
    df = base_dataframe.copy()
    target_idx = 10

    # Valid conditions except low ADX
    df.loc[target_idx, "regime_1h"] = "trend_up"
    df.loc[target_idx, "close"] = 100.5
    df.loc[target_idx, "ema200"] = 98.0
    df.loc[target_idx, "ema50"] = 99.0
    df.loc[target_idx, "ema20"] = 100.0
    df.loc[target_idx, "low"] = 99.8
    df.loc[target_idx, "open"] = 100.0
    df.loc[target_idx, "volume"] = 1200.0
    df.loc[target_idx, "vol_ma20"] = 1000.0
    df.loc[target_idx, "adx14"] = 15.0  # Below threshold
    df.loc[target_idx, "stoch_k"] = 60.0
    df.loc[target_idx, "stoch_d"] = 55.0
    df.loc[target_idx - 1, "stoch_k"] = 54.0
    df.loc[target_idx - 1, "stoch_d"] = 55.0

    result = strategy.populate_entry_trend(df, {"pair": "BTC/USDT"})

    assert result.loc[target_idx, "enter_long"] == 0


def test_low_volume_prevents_entry(strategy, base_dataframe):
    """Test that low volume prevents entry."""
    df = base_dataframe.copy()
    target_idx = 10

    # Valid conditions except low volume
    df.loc[target_idx, "regime_1h"] = "trend_up"
    df.loc[target_idx, "close"] = 100.5
    df.loc[target_idx, "ema200"] = 98.0
    df.loc[target_idx, "ema50"] = 99.0
    df.loc[target_idx, "ema20"] = 100.0
    df.loc[target_idx, "low"] = 99.8
    df.loc[target_idx, "open"] = 100.0
    df.loc[target_idx, "volume"] = 500.0  # Below threshold
    df.loc[target_idx, "vol_ma20"] = 1000.0
    df.loc[target_idx, "adx14"] = 25.0
    df.loc[target_idx, "stoch_k"] = 60.0
    df.loc[target_idx, "stoch_d"] = 55.0
    df.loc[target_idx - 1, "stoch_k"] = 54.0
    df.loc[target_idx - 1, "stoch_d"] = 55.0

    result = strategy.populate_entry_trend(df, {"pair": "BTC/USDT"})

    assert result.loc[target_idx, "enter_long"] == 0


def test_future_mutation_does_not_affect_past_signals(strategy, base_dataframe):
    """Test that modifying future rows doesn't change past signals."""
    df = base_dataframe.copy()
    target_idx = 10

    # Setup valid long at target_idx
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

    result1 = strategy.populate_entry_trend(df.copy(), {"pair": "BTC/USDT"})
    original_signal = result1.loc[target_idx, "enter_long"]

    # Mutate future rows
    df.loc[target_idx + 1 :, "regime_1h"] = "trend_down"
    df.loc[target_idx + 1 :, "volume"] = 0.0

    result2 = strategy.populate_entry_trend(df.copy(), {"pair": "BTC/USDT"})
    new_signal = result2.loc[target_idx, "enter_long"]

    assert original_signal == new_signal == 1


def test_no_simultaneous_long_and_short(strategy, base_dataframe):
    """Test that the same candle cannot fire both long and short."""
    df = base_dataframe.copy()

    # Setup conditions that might try to fire both
    df["regime_1h"] = "trend_up"
    df["close"] = 100.5
    df["open"] = 100.0
    df["volume"] = 1200.0
    df["vol_ma20"] = 1000.0
    df["adx14"] = 25.0

    result = strategy.populate_entry_trend(df, {"pair": "BTC/USDT"})

    # Check that no row has both signals
    both_signals = (result["enter_long"] == 1) & (result["enter_short"] == 1)
    assert not both_signals.any()

