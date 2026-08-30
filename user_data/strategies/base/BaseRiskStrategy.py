"""Shared, fail-closed risk controls for every trading strategy."""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from numbers import Real
from typing import Any, ClassVar

import pandas as pd
from freqtrade.enums import RunMode
from freqtrade.strategy import IStrategy, stoploss_from_open

try:  # Freqtrade adds user_data/strategies to sys.path when loading strategies.
    from lib.guards import (
        daily_loss_halt,
        funding_ok,
        liquidity_ok,
        slippage_ok,
        spread_ok,
    )
    from lib.indicators import atr
    from lib.regime import classify_regime
    from lib.risk_state import get_risk_manager
    from lib.snapshot import collect_market_snapshot, get_cache
except ModuleNotFoundError:  # Package imports used by the isolated test suite.
    from user_data.strategies.lib.guards import (
        daily_loss_halt,
        funding_ok,
        liquidity_ok,
        slippage_ok,
        spread_ok,
    )
    from user_data.strategies.lib.indicators import atr
    from user_data.strategies.lib.regime import classify_regime
    from user_data.strategies.lib.risk_state import get_risk_manager
    from user_data.strategies.lib.snapshot import collect_market_snapshot, get_cache

logger = logging.getLogger(__name__)


RISK: dict[str, float] = {
    "risk_per_trade": 0.005,
    "max_position_pct": 0.25,
    "max_open_trades": 3,
    "daily_loss_halt_pct": 2.0,
    "weekly_loss_halt_pct": 5.0,
    "max_drawdown_pct": 10.0,
    "max_leverage": 2.0,
    "min_notional": 10.0,
    "min_24h_volume": 1_000_000.0,
    "max_spread_bps": 15.0,
    "max_slippage_bps": 30.0,
    "max_funding_rate": 0.0005,
}


class BaseRiskStrategy(IStrategy):
    """Freqtrade base class with conservative sizing and entry circuit breakers."""

    INTERFACE_VERSION = 3
    can_short = True
    minimal_roi: ClassVar[dict[str, float]] = {
        "0": 0.070,
        "45": 0.048,
        "120": 0.032,
        "300": 0.020,
    }
    # Stop mechanism: Using trailing stop (not custom_stoploss)
    # custom_stoploss callback is disabled to avoid conflicts with trailing stop
    stoploss = -0.025
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.028
    trailing_only_offset_is_reached = True
    use_custom_stoploss = False  # Disabled: trailing stop is active
    use_exit_signal = False
    timeframe = "15m"
    # The 1h regime's longest rolling statistic spans 500 bars (about 21 days).
    # Four 15m bars per hour require 2,000 primary candles before it is mature.
    startup_candle_count = 2000
    process_only_new_candles = True
    position_adjustment_enable = True

    # The 1h BTC regime is a deliberately global market filter. Its timestamp
    # is shifted by a full hour in ``informative_regime`` before it is used.
    informative_market_pair = "BTC/USDC:USDC"
    informative_timeframe = "1h"

    protections: ClassVar[list[dict[str, Any]]] = [
        {"method": "CooldownPeriod", "stop_duration_candles": 3},
        {
            "method": "StoplossGuard",
            "lookback_period_candles": 6,
            "trade_limit": 2,  # At least 2 stoploss trades required
            "stop_duration_candles": 24,
            "only_per_pair": False,
            "only_per_side": False,
        },
        {
            "method": "MaxDrawdown",
            "lookback_period_candles": 100,
            "stop_duration_candles": 24,
            "max_allowed_drawdown": 0.10,
        },
        {
            "method": "LowProfitPairs",
            "lookback_period_candles": 100,
            "trade_limit": 4,  # At least 4 trades required before evaluation
            "stop_duration_candles": 24,
            "required_profit": 0.0,
        },
    ]

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        """Support both Freqtrade injection and lightweight isolated tests."""
        super().__init__(config or {})
        configured_pair = (config or {}).get("informative_market_pair")
        if isinstance(configured_pair, str) and configured_pair:
            self.informative_market_pair = configured_pair

        # Snapshot cache for execution guards
        self._snapshot_cache = get_cache()
        self._snapshot_ttl = 60.0  # seconds

        # Persistent risk state manager
        self._risk_manager = get_risk_manager(".risk_state.json")

        # Legacy in-memory tracking (kept for backward compatibility)
        self._circuit_day = None
        self._circuit_start_equity: float | None = None
        self._equity_peak: float | None = None

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict[str, Any]) -> pd.DataFrame:
        """Keep the base class instantiable for risk-unit tests and subclasses.

        Subclasses should call super().populate_indicators() to collect market snapshots.
        """
        # Collect market snapshot for execution guards (outside callback path)
        pair = metadata.get("pair")
        if pair and hasattr(self, "dp") and self.dp is not None:
            collect_market_snapshot(self.dp, pair, orderbook_depth=10)
        return dataframe

    @staticmethod
    def _finite_positive(value: Any) -> float | None:
        """Return a finite positive number, otherwise ``None``."""
        if isinstance(value, bool) or not isinstance(value, (Real, str)):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) and number > 0 else None

    def _get_analyzed_dataframe(self, pair: str) -> pd.DataFrame | None:
        """Read analyzed data defensively; DP is absent in some unit contexts."""
        data_provider = getattr(self, "dp", None)
        getter = getattr(data_provider, "get_analyzed_dataframe", None)
        if not callable(getter):
            return None
        try:
            dataframe, _ = getter(pair, self.timeframe)
        except (AttributeError, KeyError, TypeError, ValueError):
            return None
        return dataframe if isinstance(dataframe, pd.DataFrame) and not dataframe.empty else None

    def _last_closed_atr(self, dataframe: pd.DataFrame) -> float | None:
        """Return ATR from the penultimate candle, never the potentially open bar."""
        if len(dataframe) < 2:
            return None
        series = dataframe.get("atr14")
        if not isinstance(series, pd.Series):
            series = atr(dataframe, n=14)
        value = self._finite_positive(pd.to_numeric(series, errors="coerce").iloc[-2])
        return value

    def _equity(self) -> float | None:
        wallets = getattr(self, "wallets", None)
        getter = getattr(wallets, "get_total_stake_amount", None)
        if not callable(getter):
            return None
        try:
            return self._finite_positive(getter())
        except (AttributeError, TypeError, ValueError):
            return None

    def leverage(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs: Any,
    ) -> float:
        """Enforce the portfolio leverage ceiling before Freqtrade opens a trade."""
        proposed = self._finite_positive(proposed_leverage) or 1.0
        exchange_max = self._finite_positive(max_leverage) or 1.0
        return min(proposed, exchange_max, RISK["max_leverage"])

    def custom_stake_amount(
        self,
        pair: str,
        current_time: datetime,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs: Any,
    ) -> float:
        """Size collateral using fixed fractional risk and the last closed ATR.

        ``risk_capital / (ATR / price)`` is the position notional. Freqtrade
        expects collateral here, so the result is divided by leverage. A trade
        below the exchange minimum is rejected instead of being enlarged beyond
        its risk budget.
        """
        rate = self._finite_positive(current_rate)
        effective_leverage = self._finite_positive(leverage)
        dataframe = self._get_analyzed_dataframe(pair)
        if rate is None or effective_leverage is None or dataframe is None:
            return 0.0

        atr_value = self._last_closed_atr(dataframe)
        equity = self._equity()
        if atr_value is None or equity is None:
            return 0.0

        stop_fraction = atr_value / rate
        if not math.isfinite(stop_fraction) or stop_fraction <= 0:
            return 0.0
        risk_capital = equity * RISK["risk_per_trade"]
        position_notional = risk_capital / stop_fraction
        stake = position_notional / effective_leverage
        position_notional_cap = equity * RISK["max_position_pct"]
        stake_cap = position_notional_cap / effective_leverage
        exchange_cap = self._finite_positive(max_stake)
        minimum = max(
            RISK["min_notional"] / effective_leverage,
            self._finite_positive(min_stake) if min_stake is not None else 0.0,
        )
        if exchange_cap is None:
            return 0.0
        cap = min(stake_cap, exchange_cap)
        if not math.isfinite(stake) or stake < minimum or cap < minimum:
            logger.debug("Risk sizing rejected %s: stake %.8f is below safe minimum", pair, stake)
            return 0.0
        return min(stake, cap)

    def custom_stoploss(
        self,
        pair: str,
        trade: Any,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        after_fill: bool,
        **kwargs: Any,
    ) -> float:
        """Dynamic trailing and profit locking with proper fee cushion."""
        is_short = getattr(trade, "is_short", False)
        leverage = getattr(trade, "leverage", 1.0) or 1.0
        if current_profit >= 0.030:
            return -0.012
        if current_profit >= 0.018:
            return -stoploss_from_open(0.010, current_profit, is_short=is_short, leverage=leverage)
        if current_profit >= 0.010:
            return -stoploss_from_open(0.004, current_profit, is_short=is_short, leverage=leverage)
        return self.stoploss

    def custom_exit(
        self,
        pair: str,
        trade: Any,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs: Any,
    ) -> str | None:
        """Exit an invalidated trade after 48 closed candles if still underwater."""
        opened_at = getattr(trade, "open_date_utc", None)
        if not isinstance(opened_at, datetime):
            return None
        now = current_time
        if opened_at.tzinfo is None:
            opened_at = opened_at.replace(tzinfo=UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        candles_held = (now - opened_at).total_seconds() / (15 * 60)
        if math.isfinite(candles_held) and candles_held >= 48 and current_profit < -0.015:
            return "time_stop_loss"
        return None

    def _daily_start_equity(self, current_time: datetime, equity: float) -> float:
        """Use a wallet snapshot when available, else maintain a session snapshot."""
        wallets = getattr(self, "wallets", None)
        getter = getattr(wallets, "get_start_of_day_balance", None)
        if callable(getter):
            try:
                remote_start = self._finite_positive(getter())
            except (AttributeError, TypeError, ValueError):
                remote_start = None
            if remote_start is not None:
                return remote_start

        session_day = current_time.date()
        if getattr(self, "_circuit_day", None) != session_day:
            self._circuit_day = session_day
            self._circuit_start_equity = equity
        return self._finite_positive(getattr(self, "_circuit_start_equity", equity)) or equity

    def circuit_breaker_active(self, current_time: datetime) -> bool:
        """Apply independent daily-loss, weekly-loss and max-drawdown entry halts.

        Uses persistent risk state that survives restarts. Manual recovery required
        after halt activation.
        """
        # Check persistent halt first
        if self._risk_manager.is_halted():
            reason = self._risk_manager.get_halt_reason()
            logger.warning("Circuit breaker active (persistent halt): %s", reason)
            return True

        equity = self._equity()
        if equity is None:
            logger.warning("Circuit breaker active: equity unavailable")
            return True

        # Update risk state with current equity
        self._risk_manager.update_equity(equity, current_time)

        # Check all limits (each can trigger persistent halt)
        daily_halted = self._risk_manager.check_daily_loss_limit(
            RISK["daily_loss_halt_pct"], current_time
        )
        weekly_halted = self._risk_manager.check_weekly_loss_limit(
            RISK.get("weekly_loss_halt_pct", 5.0), current_time
        )
        drawdown_halted = self._risk_manager.check_drawdown_limit(
            equity, RISK["max_drawdown_pct"], current_time
        )

        return daily_halted or weekly_halted or drawdown_halted

    def confirm_trade_entry(
        self,
        pair: str,
        order_type: str,
        amount: float,
        rate: float,
        time_in_force: str,
        current_time: datetime,
        entry_tag: str | None,
        side: str,
        **kwargs: Any,
    ) -> bool:
        """Require live market data to pass every execution and risk guard.

        Reads from cached snapshot - does NOT call network APIs directly.
        Fails closed when snapshot is stale, missing, or invalid.
        """
        # Historical engines do not have a live ticker/order book. Signal and
        # bias validation must therefore exercise entries without pretending to
        # have execution data; dry-run and live modes still use every guard.
        runmode = self.config.get("runmode")
        if runmode is not None and runmode not in {
            RunMode.LIVE,
            RunMode.DRY_RUN,
            "live",
            "dry_run",
        }:
            return True

        # Get snapshot from cache (no network I/O)
        snapshot = self._snapshot_cache.get(pair, ttl_seconds=self._snapshot_ttl)

        if snapshot is None:
            logger.warning("Rejecting %s: snapshot missing", pair)
            self._snapshot_cache.record_deny(pair, "snapshot_missing")
            return False

        if not snapshot.is_valid(self._snapshot_ttl):
            if snapshot.error:
                logger.warning("Rejecting %s: snapshot error: %s", pair, snapshot.error)
                self._snapshot_cache.record_deny(pair, f"error_{snapshot.error}")
            elif snapshot.is_stale(self._snapshot_ttl):
                age = current_time.timestamp() - snapshot.timestamp if current_time else 0
                logger.warning("Rejecting %s: snapshot stale (age: %.1fs)", pair, age)
                self._snapshot_cache.record_deny(pair, "snapshot_stale")
            else:
                logger.warning("Rejecting %s: snapshot invalid", pair)
                self._snapshot_cache.record_deny(pair, "snapshot_invalid")
            return False

        ticker = snapshot.ticker
        orderbook = snapshot.orderbook

        if ticker is None or orderbook is None:
            logger.warning("Rejecting %s: snapshot incomplete", pair)
            self._snapshot_cache.record_deny(pair, "snapshot_incomplete")
            return False

        # Execute all guards using cached data
        notional = (self._finite_positive(amount) or 0.0) * (self._finite_positive(rate) or 0.0)

        if notional <= 0:
            logger.info("Rejecting %s: invalid notional", pair)
            self._snapshot_cache.record_deny(pair, "invalid_notional")
            return False

        if not spread_ok(ticker, RISK["max_spread_bps"]):
            logger.info("Rejecting %s: spread too wide", pair)
            self._snapshot_cache.record_deny(pair, "spread_reject")
            return False

        if not liquidity_ok(ticker, RISK["min_24h_volume"]):
            logger.info("Rejecting %s: insufficient liquidity", pair)
            self._snapshot_cache.record_deny(pair, "liquidity_reject")
            return False

        if not slippage_ok(orderbook, notional, RISK["max_slippage_bps"], side):
            logger.info("Rejecting %s: slippage too high", pair)
            self._snapshot_cache.record_deny(pair, "slippage_reject")
            return False

        # Funding check - fail closed if unknown
        funding_rate = ticker.get("fundingRate") if isinstance(ticker, dict) else None
        if funding_rate is None:
            logger.info("Rejecting %s: funding rate unknown", pair)
            self._snapshot_cache.record_deny(pair, "funding_unknown")
            return False

        if not funding_ok(funding_rate, RISK["max_funding_rate"]):
            logger.info("Rejecting %s: funding rate excessive: %.6f", pair, funding_rate)
            self._snapshot_cache.record_deny(pair, "funding_reject")
            return False

        # Circuit breaker check
        if self.circuit_breaker_active(current_time):
            logger.warning("Rejecting %s: circuit breaker active", pair)
            self._snapshot_cache.record_deny(pair, "circuit_breaker")
            return False

        return True

    def informative_regime(self, dataframe: pd.DataFrame) -> pd.Series:
        """Align *closed* 1h market regimes to the strategy's 15m candles.

        The source timestamp is advanced one hour before a backward as-of merge.
        Thus a 1h bar can influence a 15m bar only after that 1h interval has
        completed. Missing DP/informative data safely falls back to ``range``.
        """
        fallback = pd.Series("range", index=dataframe.index, dtype="object")
        data_provider = getattr(self, "dp", None)
        getter = getattr(data_provider, "get_pair_dataframe", None)
        if not callable(getter) or "date" not in dataframe:
            return fallback
        try:
            informative = getter(
                pair=self.informative_market_pair, timeframe=self.informative_timeframe
            )
        except (AttributeError, KeyError, TypeError, ValueError):
            return fallback
        if not isinstance(informative, pd.DataFrame) or informative.empty or "date" not in informative:
            return fallback

        informative = informative.copy()
        informative["_available_at"] = pd.to_datetime(
            informative["date"], utc=True, errors="coerce"
        ) + pd.DateOffset(hours=1)
        informative["_regime"] = classify_regime(informative)
        informative = informative.dropna(subset=["_available_at"]).sort_values("_available_at")
        base = pd.DataFrame(
            {
                "_index": dataframe.index,
                "_date": pd.to_datetime(dataframe["date"], utc=True, errors="coerce"),
            }
        ).dropna(subset=["_date"])
        if informative.empty or base.empty:
            return fallback
        merged = pd.merge_asof(
            base.sort_values("_date"),
            informative[["_available_at", "_regime"]],
            left_on="_date",
            right_on="_available_at",
            direction="backward",
        )
        aligned = pd.Series(merged["_regime"].fillna("range").to_numpy(), index=merged["_index"])
        return aligned.reindex(dataframe.index).fillna("range")

    def adjust_trade_position(
        self,
        trade: Any,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        min_stake: float | None,
        max_stake: float,
        **kwargs: Any,
    ) -> float | None:
        """Take one half-size partial exit at +1R, at most once per trade."""
        exits = getattr(trade, "nr_of_successful_exits", 0)
        stake = self._finite_positive(getattr(trade, "stake_amount", None))
        if current_profit >= 0.01 and exits == 0 and stake is not None:
            return -stake * 0.5
        return None
