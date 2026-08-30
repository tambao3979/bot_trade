"""
RobustTrend R1 - R0 + DMI directional filter.

Hypothesis: Adding DMI directional separation (-DI > +DI for shorts) removes
weak signals when directional movement is unclear, improving recent period PF.
"""

from __future__ import annotations

import pandas as pd
from freqtrade.strategy import DecimalParameter

try:
    from base.BaseRiskStrategy import BaseRiskStrategy
    from lib.indicators import adx, atr, dmi, ema, rsi, vol_ma
except ModuleNotFoundError:
    from user_data.strategies.base.BaseRiskStrategy import BaseRiskStrategy
    from user_data.strategies.lib.indicators import adx, atr, dmi, ema, rsi, vol_ma


class RobustTrendR1(BaseRiskStrategy):
    """R1: R0 + DMI directional filter (short-only)."""

    timeframe = "15m"
    process_only_new_candles = True
    use_exit_signal = False
    can_short = True

    # Hyperopt parameter for DMI threshold
    dmi_threshold = DecimalParameter(5.0, 20.0, default=10.0, space="buy")

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

        # DMI components for directional filter
        dmi_vals = dmi(dataframe, 14)
        dataframe["plus_di"] = dmi_vals["plus_di"]
        dataframe["minus_di"] = dmi_vals["minus_di"]

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

        # R1: R0 baseline + DMI directional filter
        bear_cross = (
            (dataframe["stoch_k"] < dataframe["stoch_d"])
            & (dataframe["stoch_k"].shift(1) >= dataframe["stoch_d"].shift(1))
        )

        # NEW: DMI directional filter for shorts (-DI > +DI with threshold)
        dmi_short_strength = dataframe["minus_di"] - dataframe["plus_di"]

        short_entry = (
            # Original R0 conditions
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
            # NEW: R1 DMI filter
            & (dmi_short_strength > self.dmi_threshold.value)
        )

        dataframe.loc[short_entry, "enter_short"] = 1
        dataframe.loc[short_entry, "enter_tag"] = "trend_short_dmi"

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe
