"""
Setup C – Range Reversion (T12).
"""

from __future__ import annotations

import pandas as pd

try:
    from base.BaseRiskStrategy import BaseRiskStrategy
    from lib.indicators import adx, bbands, rsi, vwap_session
except ModuleNotFoundError:
    from user_data.strategies.base.BaseRiskStrategy import BaseRiskStrategy
    from user_data.strategies.lib.indicators import adx, bbands, rsi, vwap_session


class RangeReversion(BaseRiskStrategy):
    timeframe = "15m"

    process_only_new_candles = True

    use_exit_signal = False

    can_short = True

    def informative_pairs(self):
        return [("BTC/USDC:USDC", "1h")]

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["rsi14"] = rsi(dataframe["close"], 14)
        bb = bbands(dataframe, 20, 2)
        dataframe["bb_lower"] = bb["bb_lower"]
        dataframe["bb_mid"] = bb["bb_mid"]
        dataframe["bb_upper"] = bb["bb_upper"]
        dataframe["vwap"] = vwap_session(dataframe)
        dataframe["adx14"] = adx(dataframe, 14)

        dataframe["regime_1h"] = self.informative_regime(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        is_range = (dataframe["regime_1h"] == "range") | (dataframe["adx14"] < 22)
        cond_long = (
            is_range
            & (dataframe["regime_1h"] != "chaos")
            & (dataframe["low"] <= dataframe["bb_lower"] * 1.002)
            & ((dataframe["close"] > dataframe["open"]) | (dataframe["close"] > dataframe["bb_lower"]))
            & (dataframe["rsi14"] < 38)
        )
        cond_short = (
            is_range
            & (dataframe["regime_1h"] != "chaos")
            & (dataframe["high"] >= dataframe["bb_upper"] * 0.998)
            & ((dataframe["close"] < dataframe["open"]) | (dataframe["close"] < dataframe["bb_upper"]))
            & (dataframe["rsi14"] > 62)
        )
        dataframe.loc[cond_long, "enter_long"] = 1
        dataframe.loc[cond_short, "enter_short"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe
