"""
Market regime classifier.
"""

from __future__ import annotations

import pandas as pd

from .indicators import adx, atr_pct, bbands, ema


def classify_regime(df_1h: pd.DataFrame) -> pd.Series:
    """
    Classify each 1h bar as one of:
        trend_up, trend_down, range, chaos
    """
    close = pd.to_numeric(df_1h["close"], errors="coerce")
    ema50 = ema(close, 50)
    ema200 = ema(close, 200)
    adx_ser = adx(df_1h, n=14)
    bb = bbands(df_1h, n=20, k=2)
    width = (bb["bb_upper"] - bb["bb_lower"]) / bb["bb_mid"].replace(0, pd.NA)
    atr_pct_ser = atr_pct(df_1h, n=14)
    width_rank = width.rolling(200).rank(pct=True)
    atr_threshold = atr_pct_ser.rolling(500).quantile(0.95)
    net_change = close.pct_change(50).abs()

    regime = pd.Series("chaos", index=df_1h.index)
    regime[(close > ema200) & (ema50 > ema200) & (adx_ser >= 20)] = "trend_up"
    regime[(close < ema200) & (ema50 < ema200) & (adx_ser >= 20)] = "trend_down"
    regime[(adx_ser < 18) | ((width_rank < 0.7) & (net_change < 0.02))] = "range"
    regime[atr_pct_ser > atr_threshold * 1.2] = "chaos"
    return regime.fillna("chaos")
