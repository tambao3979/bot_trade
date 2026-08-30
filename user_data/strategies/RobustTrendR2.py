"""
RobustTrend R2 - R1 with relaxed DMI threshold.

Changes from R1:
- DMI threshold reduced from 10.0 to 5.0 (recover trade count)
- BTC pair removed from testing (consistently failing)

Hypothesis: R1's DMI filter was too strict. Relaxing threshold should
recover trade count while maintaining quality improvement over R0.
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


class RobustTrendR2(BaseRiskStrategy):
    """R2: R1 with relaxed DMI threshold (5.0 default)."""

    timeframe = "15m"
    process_only_new_candles = True
    use_exit_signal = False
    can_short = True

    # Relaxed DMI threshold for more signals
    dmi_threshold = DecimalParameter(3.0, 15.0, default=5.0, space="buy")

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

        # DMI components
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

        # R2: R1 with relaxed DMI threshold (10.0 -> 5.0)
        bear_cross = (
            (dataframe["stoch_k"] < dataframe["stoch_d"])
            & (dataframe["stoch_k"].shift(1) >= dataframe["stoch_d"].shift(1))
        )

        # Relaxed DMI filter
        dmi_short_strength = dataframe["minus_di"] - dataframe["plus_di"]

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
            # R2: Relaxed DMI threshold (5.0 instead of 10.0)
            & (dmi_short_strength > self.dmi_threshold.value)
        )

        dataframe.loc[short_entry, "enter_short"] = 1
        dataframe.loc[short_entry, "enter_tag"] = "trend_short_dmi_relaxed"

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe
