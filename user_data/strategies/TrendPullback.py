"""
Setup A – Trend Pullback (T10).
Long: pullback into EMA, RSI momentum, volume confirmation.
Short: mirror image.
"""

from __future__ import annotations

import pandas as pd
from freqtrade.strategy import DecimalParameter

try:
    from base.BaseRiskStrategy import BaseRiskStrategy
    from lib.indicators import adx, atr, ema, rsi, vol_ma
except ModuleNotFoundError:
    from user_data.strategies.base.BaseRiskStrategy import BaseRiskStrategy
    from user_data.strategies.lib.indicators import adx, atr, ema, rsi, vol_ma


class TrendPullback(BaseRiskStrategy):
    timeframe = "15m"

    process_only_new_candles = True

    use_exit_signal = False

    can_short = True

    # Hyperopt parameters
    volume_mult = DecimalParameter(0.5, 1.2, default=0.8, space="buy")
    stoch_upper = DecimalParameter(60.0, 80.0, default=70.0, space="buy")
    stoch_lower = DecimalParameter(20.0, 40.0, default=30.0, space="buy")

    def informative_pairs(self):
        return [("BTC/USDC:USDC", "1h"), ("ETH/USDC:USDC", "1h")]

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
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

        dataframe["regime_1h"] = self.informative_regime(dataframe)

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

        # Long setup: bullish cross after pullback to EMA20
        bull_cross = (
            (dataframe["stoch_k"] > dataframe["stoch_d"])
            & (dataframe["stoch_k"].shift(1) <= dataframe["stoch_d"].shift(1))
        )
        cond_long = (
            (dataframe["regime_1h"] == "trend_up")
            & (dataframe["close"] > dataframe["ema200"])
            & (dataframe["close"] > dataframe["ema50"])
            & (dataframe["ema20"] > dataframe["ema50"])
            & (dataframe["low"] <= dataframe["ema20"] * 1.003)
            & (dataframe["close"] > dataframe["ema20"])
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["stoch_k"] < self.stoch_upper.value)
            & bull_cross
            & (dataframe["adx14"] > 20)
            & (dataframe["volume"] > self.volume_mult.value * dataframe["vol_ma20"])
        )

        # Short setup: bearish cross after pullback to EMA20
        bear_cross = (
            (dataframe["stoch_k"] < dataframe["stoch_d"])
            & (dataframe["stoch_k"].shift(1) >= dataframe["stoch_d"].shift(1))
        )
        cond_short = (
            (dataframe["regime_1h"] == "trend_down")
            & (dataframe["close"] < dataframe["ema200"])
            & (dataframe["close"] < dataframe["ema50"])
            & (dataframe["ema20"] < dataframe["ema50"])
            & (dataframe["high"] >= dataframe["ema20"] * 0.997)
            & (dataframe["close"] < dataframe["ema20"])
            & (dataframe["close"] < dataframe["open"])
            & (dataframe["stoch_k"] > self.stoch_lower.value)
            & bear_cross
            & (dataframe["adx14"] > 20)
            & (dataframe["volume"] > self.volume_mult.value * dataframe["vol_ma20"])
        )

        dataframe.loc[cond_long, "enter_long"] = 1
        dataframe.loc[cond_long, "enter_tag"] = "trend_pullback_long"
        dataframe.loc[cond_short, "enter_short"] = 1
        dataframe.loc[cond_short, "enter_tag"] = "trend_pullback_short"
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe
