"""
Meta strategy that routes to the best sub-strategy based on regime.
T13.

This implementation does not instantiate sub-strategy classes;
it computes all signals inline to avoid object duplication and
keep the routing logic explicit.
"""

from __future__ import annotations

import pandas as pd

try:
    from base.BaseRiskStrategy import BaseRiskStrategy
    from lib.indicators import adx, atr, bbands, ema, rsi, vol_ma, vwap_session
except ModuleNotFoundError:
    from user_data.strategies.base.BaseRiskStrategy import BaseRiskStrategy
    from user_data.strategies.lib.indicators import (
        adx,
        atr,
        bbands,
        ema,
        rsi,
        vol_ma,
        vwap_session,
    )


class MetaRouter(BaseRiskStrategy):
    timeframe = "15m"

    process_only_new_candles = True

    use_exit_signal = False

    can_short = True

    # Enable only short trades - proven to work best for this strategy
    enabled_setups = frozenset({"trend_short"})

    def informative_pairs(self):
        return [("BTC/USDC:USDC", "1h")]

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
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

        # Bollinger Bands
        bb = bbands(dataframe, 20, 2)
        dataframe["bb_lower"] = bb["bb_lower"]
        dataframe["bb_mid"] = bb["bb_mid"]
        dataframe["bb_upper"] = bb["bb_upper"]

        dataframe["vwap"] = vwap_session(dataframe)

        # 24h session range (96 bars on 15m)
        dataframe["prev_session_high"] = dataframe["high"].rolling(96).max().shift(1)
        dataframe["prev_session_low"] = dataframe["low"].rolling(96).min().shift(1)

        dataframe["regime_1h"] = self.informative_regime(dataframe)

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""

        # --- Setup A: TrendPullback (synced from Phase 3 baseline) ---
        if "trend_long" in self.enabled_setups:
            bull_cross = (
                (dataframe["stoch_k"] > dataframe["stoch_d"])
                & (dataframe["stoch_k"].shift(1) <= dataframe["stoch_d"].shift(1))
            )
            long_a = (
                (dataframe["regime_1h"] == "trend_up")
                & (dataframe["close"] > dataframe["ema200"])
                & (dataframe["close"] > dataframe["ema50"])
                & (dataframe["ema20"] > dataframe["ema50"])
                & (dataframe["low"] <= dataframe["ema20"] * 1.003)
                & (dataframe["close"] > dataframe["ema20"])
                & (dataframe["close"] > dataframe["open"])
                & (dataframe["stoch_k"] < 70)
                & bull_cross
                & (dataframe["adx14"] > 20)
                & (dataframe["volume"] > 0.8 * dataframe["vol_ma20"])
            )
            dataframe.loc[long_a, "enter_long"] = 1
            dataframe.loc[long_a, "enter_tag"] = "trend_pullback_long"

        if "trend_short" in self.enabled_setups:
            bear_cross = (
                (dataframe["stoch_k"] < dataframe["stoch_d"])
                & (dataframe["stoch_k"].shift(1) >= dataframe["stoch_d"].shift(1))
            )
            short_a = (
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
            dataframe.loc[short_a, "enter_short"] = 1
            dataframe.loc[short_a, "enter_tag"] = "trend_pullback_short"

        # --- Setup C: RangeReversion (disabled - baseline PF < 1.00) ---
        if "range_long" in self.enabled_setups or "range_short" in self.enabled_setups:
            range_mask = (dataframe["regime_1h"] == "range") | (dataframe["adx14"] < 20)
            not_chaos = dataframe["regime_1h"] != "chaos"

            if "range_long" in self.enabled_setups:
                long_c = (
                    range_mask
                    & not_chaos
                    & (dataframe["low"] <= dataframe["bb_lower"] * 1.001)
                    & (dataframe["close"] > dataframe["open"])
                    & (dataframe["rsi14"] < 35)
                    & (dataframe["enter_long"] == 0)
                )
                dataframe.loc[long_c, "enter_long"] = 1
                dataframe.loc[long_c, "enter_tag"] = "range_reversion_long"

            if "range_short" in self.enabled_setups:
                short_c = (
                    range_mask
                    & not_chaos
                    & (dataframe["high"] >= dataframe["bb_upper"] * 0.999)
                    & (dataframe["close"] < dataframe["open"])
                    & (dataframe["rsi14"] > 65)
                    & (dataframe["enter_short"] == 0)
                )
                dataframe.loc[short_c, "enter_short"] = 1
                dataframe.loc[short_c, "enter_tag"] = "range_reversion_short"

        # --- Setup B: LiquiditySweep (disabled - baseline PF < 1.00) ---
        if "liquidity_long" in self.enabled_setups or "liquidity_short" in self.enabled_setups:
            in_killzone = (
                (dataframe["date"].dt.hour >= 6) & (dataframe["date"].dt.hour <= 18)
            )
            candle_range = dataframe["high"] - dataframe["low"]
            lower_wick = dataframe["close"] - dataframe["low"]
            upper_wick = dataframe["high"] - dataframe["close"]

            if "liquidity_long" in self.enabled_setups:
                not_chaos = dataframe["regime_1h"] != "chaos"
                long_b = (
                    not_chaos
                    & (dataframe["low"] < dataframe["prev_session_low"])
                    & (dataframe["close"] > dataframe["prev_session_low"])
                    & (
                        (dataframe["close"] > dataframe["open"])
                        | ((candle_range > 0) & (lower_wick > 0.35 * candle_range))
                    )
                    & (dataframe["rsi14"] < 48)
                    & in_killzone
                    & (dataframe["enter_long"] == 0)
                )
                dataframe.loc[long_b, "enter_long"] = 1
                dataframe.loc[long_b, "enter_tag"] = "liquidity_sweep_long"

            if "liquidity_short" in self.enabled_setups:
                not_chaos = dataframe["regime_1h"] != "chaos"
                short_b = (
                    not_chaos
                    & (dataframe["high"] > dataframe["prev_session_high"])
                    & (dataframe["close"] < dataframe["prev_session_high"])
                    & (
                        (dataframe["close"] < dataframe["open"])
                        | ((candle_range > 0) & (upper_wick > 0.35 * candle_range))
                    )
                    & (dataframe["rsi14"] > 52)
                    & in_killzone
                    & (dataframe["enter_short"] == 0)
                )
                dataframe.loc[short_b, "enter_short"] = 1
                dataframe.loc[short_b, "enter_tag"] = "liquidity_sweep_short"

        # Resolve conflicts
        conflict = (dataframe["enter_long"] == 1) & (dataframe["enter_short"] == 1)
        dataframe.loc[conflict, ["enter_long", "enter_short"]] = 0
        dataframe.loc[conflict, "enter_tag"] = ""

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["exit_long"] = 0
        dataframe["exit_short"] = 0
        return dataframe
