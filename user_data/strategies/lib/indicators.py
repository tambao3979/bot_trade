"""
Indicator library used by all strategies.
Contains no-lookahead helpers implemented with pandas/numpy.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _numeric(series: pd.Series) -> pd.Series:
    """Coerce an input to finite numeric values without backfilling history."""
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def ema(series: pd.Series, n: int) -> pd.Series:
    """Exponential moving average."""
    return _numeric(series).ewm(span=n, adjust=False).mean()


def rsi(series: pd.Series, n: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = _numeric(series).diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    result = result.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    result = result.mask((avg_loss == 0) & (avg_gain == 0), 50.0)
    return result.clip(lower=0, upper=100).replace([np.inf, -np.inf], np.nan)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Average True Range."""
    high = _numeric(df["high"])
    low = _numeric(df["low"])
    close = _numeric(df["close"])
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, min_periods=n, adjust=False).mean().replace(
        [np.inf, -np.inf], np.nan
    )


def atr_pct(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """ATR as a percentage of close."""
    close = _numeric(df["close"]).replace(0, np.nan)
    return (atr(df, n) / close).replace([np.inf, -np.inf], np.nan)


def bbands(
    df: pd.DataFrame, n: int = 20, k: float = 2.0
) -> pd.DataFrame:
    """Bollinger Bands."""
    close = _numeric(df["close"])
    mid = close.rolling(n).mean()
    std = close.rolling(n).std()
    upper = mid + k * std
    lower = mid - k * std
    return pd.DataFrame({"bb_mid": mid, "bb_upper": upper, "bb_lower": lower})


def vwap_session(df: pd.DataFrame) -> pd.Series:
    """VWAP reset at each UTC day, computed only from candles seen so far."""
    typical = (_numeric(df["high"]) + _numeric(df["low"]) + _numeric(df["close"])) / 3
    volume = _numeric(df["volume"]).clip(lower=0)
    weighted_price = typical * volume

    if "date" in df:
        session = pd.to_datetime(df["date"], utc=True, errors="coerce").dt.floor("D")
        cumulative_volume = volume.groupby(session, sort=False).cumsum()
        cumulative_price = weighted_price.groupby(session, sort=False).cumsum()
    else:
        cumulative_volume = volume.cumsum()
        cumulative_price = weighted_price.cumsum()

    return (cumulative_price / cumulative_volume.replace(0, np.nan)).replace(
        [np.inf, -np.inf], np.nan
    )


def dmi(df: pd.DataFrame, n: int = 14) -> dict[str, pd.Series]:
    """Directional Movement Index - returns +DI and -DI components."""
    high = _numeric(df["high"])
    low = _numeric(df["low"])
    close = _numeric(df["close"])
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)
    atr_ = tr.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()

    plus_dm_series = pd.Series(plus_dm, index=df.index)
    minus_dm_series = pd.Series(minus_dm, index=df.index)

    plus_di = (
        100
        * plus_dm_series.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
        / atr_.replace(0, np.nan)
    )
    minus_di = (
        100
        * minus_dm_series.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
        / atr_.replace(0, np.nan)
    )

    return {
        "plus_di": plus_di.replace([np.inf, -np.inf], np.nan),
        "minus_di": minus_di.replace([np.inf, -np.inf], np.nan),
    }


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """Average Directional Index."""
    dmi_vals = dmi(df, n)
    plus_di = dmi_vals["plus_di"]
    minus_di = dmi_vals["minus_di"]
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
    return dx.ewm(alpha=1 / n, min_periods=n, adjust=False).mean().clip(0, 100).replace(
        [np.inf, -np.inf], np.nan
    )


def vol_ma(df: pd.DataFrame, n: int = 20) -> pd.Series:
    """Volume moving average."""
    return _numeric(df["volume"]).clip(lower=0).rolling(n).mean()
