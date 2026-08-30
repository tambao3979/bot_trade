"""
Tests for lib/regime.py (T06).
"""

import numpy as np
import pandas as pd

from user_data.strategies.lib.regime import classify_regime


def test_trend_up_detected():
    dates = pd.date_range("2020-01-01", periods=500, freq="1h")
    close = np.linspace(100, 300, 500)
    df = pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": np.ones(500) * 100,
        }
    )
    regime = classify_regime(df)
    assert (regime.tail(10) == "trend_up").any()


def test_range_detected():
    dates = pd.date_range("2020-01-01", periods=500, freq="1h")
    close = 100 + 5 * np.sin(np.linspace(0, 10 * np.pi, 500))
    df = pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": np.ones(500) * 100,
        }
    )
    regime = classify_regime(df)
    assert (regime.tail(10) == "range").any()
