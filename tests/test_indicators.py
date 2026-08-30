"""
Tests for lib/indicators.py (T05).
"""

import numpy as np
import pandas as pd

from user_data.strategies.lib.indicators import (
    adx,
    atr,
    bbands,
    ema,
    rsi,
    vol_ma,
    vwap_session,
)


def _sample_df() -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=50, freq="15min")
    return pd.DataFrame(
        {
            "date": dates,
            "open": np.linspace(100, 150, 50),
            "high": np.linspace(101, 151, 50),
            "low": np.linspace(99, 149, 50),
            "close": np.linspace(100, 150, 50),
            "volume": np.ones(50) * 1000,
        }
    )


def test_ema_known_value():
    df = _sample_df()
    result = ema(df["close"], 3)
    assert not result.isna().all()
    # known manually computed value
    assert abs(result.iloc[2] - 101.0) < 1.0


def test_ema_no_nan_in_non_initial():
    df = _sample_df()
    result = ema(df["close"], 3)
    assert result.iloc[5:].notna().all()


def test_rsi_bounded():
    df = _sample_df()
    result = rsi(df["close"], 14)
    assert result.dropna().between(0, 100).all()


def test_atr_positive():
    df = _sample_df()
    result = atr(df)
    assert (result.dropna() >= 0).all()


def test_bbands_upper_above_lower():
    df = _sample_df()
    bb = bbands(df)
    valid = bb.dropna()
    assert not valid.empty
    assert (valid["bb_upper"] > valid["bb_lower"]).all()


def test_vwap_positive():
    df = _sample_df()
    result = vwap_session(df)
    assert (result.dropna() > 0).all()


def test_vwap_resets_at_the_utc_session_boundary():
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2024-01-01T23:45:00Z", "2024-01-02T00:00:00Z", "2024-01-02T00:15:00Z"]
            ),
            "high": [102.0, 202.0, 202.0],
            "low": [98.0, 198.0, 198.0],
            "close": [100.0, 200.0, 200.0],
            "volume": [10.0, 10.0, 10.0],
        }
    )

    assert vwap_session(df).iloc[-1] == 200.0


def test_adx_between_0_100():
    df = _sample_df()
    result = adx(df)
    assert result.dropna().between(0, 100).all()


def test_vol_ma_no_nan_after_window():
    df = _sample_df()
    result = vol_ma(df, 20)
    assert result.iloc[20:].notna().all()
