"""
Setup B – Liquidity Sweep (T11).
"""

from __future__ import annotations

import pandas as pd

try:
    from base.BaseRiskStrategy import BaseRiskStrategy
    from lib.indicators import atr, rsi
except ModuleNotFoundError:
    from user_data.strategies.base.BaseRiskStrategy import BaseRiskStrategy
    from user_data.strategies.lib.indicators import atr, rsi


class LiquiditySweep(BaseRiskStrategy):
    timeframe = "15m"

    process_only_new_candles = True

    use_exit_signal = False

    can_short = True

    # Configurable killzone hours (UTC)
    killzone_start = 6
    killzone_end = 18

    def informative_pairs(self):
        return [("BTC/USDC:USDC", "1h")]

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["atr14"] = atr(dataframe, 14)
        dataframe["rsi14"] = rsi(dataframe["close"], 14)
        dataframe["regime_1h"] = self.informative_regime(dataframe)

        # 24-hour high/low (96 bars on 15m)
        dataframe["prev_session_high"] = dataframe["high"].rolling(96).max().shift(1)
        dataframe["prev_session_low"] = dataframe["low"].rolling(96).min().shift(1)
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        in_killzone = (
            (dataframe["date"].dt.hour >= self.killzone_start)
            & (dataframe["date"].dt.hour <= self.killzone_end)
        )
        candle_range = dataframe["high"] - dataframe["low"]
        lower_wick = dataframe["close"] - dataframe["low"]
        upper_wick = dataframe["high"] - dataframe["close"]

        # Long: sweeps below previous 24h low, rejects, and closes back above
        cond_long = (
            (dataframe["regime_1h"] != "chaos")
            & (dataframe["low"] < dataframe["prev_session_low"])
            & (dataframe["close"] > dataframe["prev_session_low"])
            & ((dataframe["close"] > dataframe["open"]) | ((candle_range > 0) & (lower_wick > 0.35 * candle_range)))
            & (dataframe["rsi14"] < 48)
            & (dataframe["volume"] > 0)
            & in_killzone
        )
        # Short: sweeps above previous 24h high, rejects, and closes back below
        cond_short = (
            (dataframe["regime_1h"] != "chaos")
            & (dataframe["high"] > dataframe["prev_session_high"])
            & (dataframe["close"] < dataframe["prev_session_high"])
            & ((dataframe["close"] < dataframe["open"]) | ((candle_range > 0) & (upper_wick > 0.35 * candle_range)))
            & (dataframe["rsi14"] > 52)
            & (dataframe["volume"] > 0)
            & in_killzone
        )
        dataframe.loc[cond_long, "enter_long"] = 1
        dataframe.loc[cond_short, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe
