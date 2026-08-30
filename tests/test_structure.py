"""
Tests for lib/structure.py (T07).
"""

import numpy as np
import pandas as pd

from user_data.strategies.lib.structure import detect_fvg, sweep_level, swing_points


def test_swing_points_basic():
    dates = pd.date_range("2020-01-01", periods=20, freq="15min")
    df = pd.DataFrame(
        {
            "date": dates,
            "high": [1 + i % 3 for i in range(20)],
            "low": [0 + i % 3 for i in range(20)],
            "close": [1 + i % 3 for i in range(20)],
            "volume": [100] * 20,
        }
    )
    result = swing_points(df)
    assert "is_swing_high" in result.columns
    assert "is_swing_low" in result.columns


def test_detect_fvg_returns_list():
    dates = pd.date_range("2020-01-01", periods=20, freq="15min")
    close = np.linspace(100, 110, 20)
    df = pd.DataFrame(
        {
            "date": dates,
            "high": close + 2,
            "low": close - 2,
            "close": close,
            "volume": [100] * 20,
        }
    )
    gaps = detect_fvg(df)
    assert isinstance(gaps, list)


def test_sweep_level_true():
    dates = pd.date_range("2020-01-01", periods=10, freq="15min")
    df = pd.DataFrame(
        {
            "date": dates,
            "high": [10.0] * 10,
            "low": [9.0] * 10,
            "close": [9.5] * 10,
            "volume": [100] * 10,
        }
    )
    # Force a sweep in the last row
    df.loc[df.index[-1], "low"] = 8.5
    df.loc[df.index[-1], "close"] = 9.2
    assert sweep_level(df, level=9.0)
