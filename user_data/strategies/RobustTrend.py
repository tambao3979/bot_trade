"""
RobustTrend - Short-only research strategy (PRO-HARDENING-001).

R0: MetaRouter trend_short baseline with corrected measurement.
Hypothesis: Short-only focus addresses long side decay.

DO NOT MODIFY THIS FILE DURING HYPEROPT. Create new candidates (R1, R2, etc.)
by copying and modifying specific conditions.
"""

from __future__ import annotations

import pandas as pd

try:
    from base.BaseRiskStrategy import BaseRiskStrategy
    from lib.indicators import adx, atr, ema, rsi, vol_ma
except ModuleNotFoundError:
    from user_data.strategies.base.BaseRiskStrategy import BaseRiskStrategy
    from user_data.strategies.lib.indicators import adx, atr, ema, rsi, vol_ma


class RobustTrend(BaseRiskStrategy):
    """R0: MetaRouter trend_short baseline (short-only)."""

    timeframe = "15m"
    process_only_new_candles = True
    use_exit_signal = False
    can_short = True

    def informative_pairs(self):
        return [("BTC/USDC:USDC", "1h")]

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # Call parent to collect market snapshots
        dataframe = super().populate_indicators(dataframe, metadata)

        # Core indicators
        dataframe["ema20"] = ema(dataframe["close"], 20)
        dataframe["ema50"] = ema(dataframe["close"], 50)
        dataframe["ema200"] = ema(dataframe["close"], 200)
        dataframe["rsi14"] = rsi(dataframe["close"], 14)
        dataframe["atr14"] = atr(dataframe, 14)
        dataframe["vol_ma20"] = vol_ma(dataframe, 20)
        dataframe["adx14"] = adx(dataframe, 14)

        # Stoch RSI
        rsi_val = dataframe["rsi14"]
        rsi_low = rsi_val.rolling(14).min()
        rsi_high = rsi_val.rolling(14).max()
        stoch_k = 100 * (rsi_val - rsi_low) / (rsi_high - rsi_low).replace(0, 1)
        dataframe["stoch_k"] = stoch_k
        dataframe["stoch_d"] = stoch_k.rolling(3).mean()

        # 1h regime
        dataframe["regime_1h"] = self.informative_regime(dataframe)

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

        # R0: Short-only baseline (from MetaRouter trend_short)
        bear_cross = (
            (dataframe["stoch_k"] < dataframe["stoch_d"])
            & (dataframe["stoch_k"].shift(1) >= dataframe["stoch_d"].shift(1))
        )

        short_entry = (
            (dataframe["regime_1h"] == "trend_down")
            & (dataframe["close"] < dataframe["ema200"])
            & (dataframe["close"] < dataframe["ema50"])
            & (dataframe["ema20"] < dataframe["ema50"])
            & (dataframe["high"] >= dataframe["ema20"] * 0.997)
            & (dataframe["close"] < dataframe["ema20"])
            & (dataframe["close"] < dataframe["open"])
            & (dataframe["stoch_k"] > 30)
            & bear_cross
            & (dataframe["adx14"] > 20)
            & (dataframe["volume"] > 0.8 * dataframe["vol_ma20"])
        )

        dataframe.loc[short_entry, "enter_short"] = 1
        dataframe.loc[short_entry, "enter_tag"] = "trend_short"

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe
