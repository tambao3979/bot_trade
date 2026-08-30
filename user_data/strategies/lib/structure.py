"""Price-structure helpers that only emit information known at that time."""

from __future__ import annotations

import pandas as pd

from .indicators import atr


def swing_points(df: pd.DataFrame, left: int = 3, right: int = 3) -> pd.DataFrame:
    """Detect confirmed swings without consuming a future candle.

    A pivot is emitted only when its ``right`` confirmation candles have
    closed. Its timestamp is therefore later than the pivot itself, which is
    the required trade-off for lookahead-safe live and backtest behaviour.
    """
    if left < 1 or right < 1:
        raise ValueError("left and right must both be positive")
    window = left + right + 1
    highs = pd.to_numeric(df["high"], errors="coerce").rolling(window).max()
    lows = pd.to_numeric(df["low"], errors="coerce").rolling(window).min()
    return pd.DataFrame(
        {
            "is_swing_high": (df["high"].shift(right) == highs).fillna(False),
            "is_swing_low": (df["low"].shift(right) == lows).fillna(False),
        },
        index=df.index,
    )


def last_impulse_leg(df: pd.DataFrame) -> tuple[object, object, int]:
    """Find the two most recently confirmed swing observations."""
    if df.empty:
        raise ValueError("cannot find an impulse leg in an empty dataframe")
    sw = swing_points(df)
    swing_idx = df.index[sw["is_swing_high"] | sw["is_swing_low"]]
    if len(swing_idx) < 2:
        return (df.index[0], df.index[-1], 1)
    start = swing_idx[-2]
    end = swing_idx[-1]
    direction = 1 if df.loc[end, "close"] >= df.loc[start, "close"] else -1
    return (start, end, direction)


def fib_zone(leg: tuple[object, object, int], lo: float = 0.382, hi: float = 0.618) -> tuple[float, float]:
    """Validate and return the configured retracement-band ratios.

    Price levels require the leg's prices, which this small helper does not
    receive. Returning ratios is intentional and avoids fabricating prices.
    """
    if len(leg) != 3 or not 0 < lo < hi < 1:
        raise ValueError("leg must contain three values and 0 < lo < hi < 1")
    return (lo, hi)


def detect_fvg(df: pd.DataFrame, atr_mult: float = 1.5) -> list[tuple[float, float, object]]:
    """Detect FVGs once the third candle has closed, without future data."""
    gaps: list[tuple[float, float, object]] = []
    if len(df) < 3:
        return gaps
    atr_ser = atr(df, n=14)
    for i in range(2, len(df)):
        first_high = df.iloc[i - 2]["high"]
        first_low = df.iloc[i - 2]["low"]
        middle_high = df.iloc[i - 1]["high"]
        middle_low = df.iloc[i - 1]["low"]
        current_low = df.iloc[i]["low"]
        current_high = df.iloc[i]["high"]
        threshold = atr_mult * atr_ser.iloc[i - 1]
        middle_range = abs(middle_high - middle_low)
        if pd.notna(threshold) and middle_range > threshold:
            if first_high < current_low:
                gaps.append((first_high, current_low, df.index[i]))
            if first_low > current_high:
                gaps.append((current_high, first_low, df.index[i]))
    return gaps


def sweep_level(df: pd.DataFrame, level: float, max_bars_back: int = 3) -> bool:
    """Return whether a recent closed candle swept and rejected ``level``."""
    if not pd.notna(level) or max_bars_back < 1:
        return False
    for i in range(max(0, len(df) - max_bars_back), len(df)):
        row = df.iloc[i]
        if row["low"] < level and row["close"] > level:
            return True
        if row["high"] > level and row["close"] < level:
            return True
    return False


def prev_session_range(
    df: pd.DataFrame, session: str = "asia", tz: str = "UTC"
) -> tuple[float, float]:
    """Return the preceding rolling-session proxy used by 15-minute strategies."""
    if len(df) < 2:
        return (0.0, 0.0)
    previous = df.iloc[:-1]
    return (float(previous["high"].max()), float(previous["low"].min()))
