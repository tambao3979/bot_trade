"""Persistent risk state with atomic writes and fail-closed recovery.

Daily and weekly loss limits persist across restarts. State corruption or
staleness causes entry denial until manually resolved.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RiskState:
    """Persistent risk tracking state."""

    # Daily tracking (resets at UTC midnight)
    daily_realized_pnl: float = 0.0
    daily_start_equity: float | None = None
    daily_reset_date: str | None = None  # ISO date in UTC

    # Weekly tracking (resets Monday UTC midnight)
    weekly_realized_pnl: float = 0.0
    weekly_start_equity: float | None = None
    weekly_reset_date: str | None = None  # ISO week start date

    # Peak tracking
    peak_equity: float | None = None

    # Halt state
    halt_active: bool = False
    halt_reason: str | None = None
    halt_since: str | None = None  # ISO timestamp UTC

    # Metadata
    schema_version: int = 1
    updated_at: str | None = None  # ISO timestamp UTC

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RiskState:
        """Load from dict with validation."""
        schema = data.get("schema_version", 1)
        if schema != 1:
            raise ValueError(f"Unsupported schema version: {schema}")
        return cls(**{k: v for k, v in data.items() if k in cls.__annotations__})


class RiskStateManager:
    """Atomic persistent risk state with fail-closed recovery."""

    def __init__(self, state_file: Path | str = ".risk_state.json"):
        self.state_file = Path(state_file)
        self._state = RiskState()
        self._load()

    def _load(self) -> None:
        """Load state from disk. Fail-closed on corruption."""
        if not self.state_file.exists():
            logger.info("Risk state file does not exist, starting fresh")
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._state = RiskState.from_dict(data)
            logger.info("Loaded risk state from %s", self.state_file)
        except (json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
            logger.error("Corrupted risk state file: %s", e)
            # Fail closed: keep halt active until manual recovery
            self._state = RiskState(
                halt_active=True,
                halt_reason=f"state_corruption: {type(e).__name__}",
                halt_since=datetime.now(UTC).isoformat(),
            )

    def _save(self) -> None:
        """Atomically save state to disk."""
        self._state.updated_at = datetime.now(UTC).isoformat()

        # Write to temp file first
        fd, temp_path = tempfile.mkstemp(
            dir=self.state_file.parent,
            prefix=".risk_state_tmp_",
            suffix=".json",
            text=True,
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._state.to_dict(), f, indent=2)

            # Atomic replace
            os.replace(temp_path, self.state_file)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    def get_state(self) -> RiskState:
        """Get current risk state (read-only copy)."""
        return RiskState(**asdict(self._state))

    def check_daily_reset(self, current_time: datetime) -> bool:
        """Check if daily tracking should reset. Returns True if reset occurred."""
        utc_date = current_time.astimezone(UTC).date().isoformat()

        if self._state.daily_reset_date != utc_date:
            logger.info("Daily reset: %s -> %s", self._state.daily_reset_date, utc_date)
            self._state.daily_realized_pnl = 0.0
            self._state.daily_start_equity = None
            self._state.daily_reset_date = utc_date
            self._save()
            return True
        return False

    def check_weekly_reset(self, current_time: datetime) -> bool:
        """Check if weekly tracking should reset (Monday UTC). Returns True if reset."""
        utc_dt = current_time.astimezone(UTC)
        # Get Monday of current week
        days_since_monday = utc_dt.weekday()
        week_start = (utc_dt.date() - __import__("datetime").timedelta(days=days_since_monday)).isoformat()

        if self._state.weekly_reset_date != week_start:
            logger.info("Weekly reset: %s -> %s", self._state.weekly_reset_date, week_start)
            self._state.weekly_realized_pnl = 0.0
            self._state.weekly_start_equity = None
            self._state.weekly_reset_date = week_start
            self._save()
            return True
        return False

    def update_equity(self, current_equity: float, current_time: datetime) -> None:
        """Update equity tracking. Call after each trade or periodically."""
        self.check_daily_reset(current_time)
        self.check_weekly_reset(current_time)

        # Initialize start equity if needed
        if self._state.daily_start_equity is None:
            self._state.daily_start_equity = current_equity
        if self._state.weekly_start_equity is None:
            self._state.weekly_start_equity = current_equity

        # Update peak
        if self._state.peak_equity is None or current_equity > self._state.peak_equity:
            self._state.peak_equity = current_equity

        self._save()

    def record_trade_pnl(self, pnl: float, current_time: datetime) -> None:
        """Record realized PnL from a trade."""
        self.check_daily_reset(current_time)
        self.check_weekly_reset(current_time)

        self._state.daily_realized_pnl += pnl
        self._state.weekly_realized_pnl += pnl
        self._save()

    def set_halt(self, reason: str, current_time: datetime) -> None:
        """Activate halt with reason. Persists across restarts."""
        if not self._state.halt_active:
            logger.warning("Risk halt activated: %s", reason)
            self._state.halt_active = True
            self._state.halt_reason = reason
            self._state.halt_since = current_time.isoformat()
            self._save()

    def clear_halt(self) -> None:
        """Manually clear halt. Requires explicit action."""
        logger.info("Risk halt cleared (manual)")
        self._state.halt_active = False
        self._state.halt_reason = None
        self._state.halt_since = None
        self._save()

    def is_halted(self) -> bool:
        """Check if halt is active."""
        return self._state.halt_active

    def get_halt_reason(self) -> str | None:
        """Get current halt reason if halted."""
        return self._state.halt_reason if self._state.halt_active else None

    def check_daily_loss_limit(self, max_loss_pct: float, current_time: datetime) -> bool:
        """Check if daily loss limit breached. Returns True if should halt."""
        self.check_daily_reset(current_time)

        if self._state.daily_start_equity is None or self._state.daily_start_equity <= 0:
            return False

        loss_pct = (-self._state.daily_realized_pnl / self._state.daily_start_equity) * 100

        if loss_pct >= max_loss_pct:
            self.set_halt(f"daily_loss_{loss_pct:.2f}%", current_time)
            return True
        return False

    def check_weekly_loss_limit(self, max_loss_pct: float, current_time: datetime) -> bool:
        """Check if weekly loss limit breached. Returns True if should halt."""
        self.check_weekly_reset(current_time)

        if self._state.weekly_start_equity is None or self._state.weekly_start_equity <= 0:
            return False

        loss_pct = (-self._state.weekly_realized_pnl / self._state.weekly_start_equity) * 100

        if loss_pct >= max_loss_pct:
            self.set_halt(f"weekly_loss_{loss_pct:.2f}%", current_time)
            return True
        return False

    def check_drawdown_limit(
        self, current_equity: float, max_dd_pct: float, current_time: datetime
    ) -> bool:
        """Check if drawdown from peak exceeds limit. Returns True if should halt."""
        if self._state.peak_equity is None or self._state.peak_equity <= 0:
            return False

        dd_pct = ((self._state.peak_equity - current_equity) / self._state.peak_equity) * 100

        if dd_pct >= max_dd_pct:
            self.set_halt(f"drawdown_{dd_pct:.2f}%", current_time)
            return True
        return False


# Global singleton for strategies
_global_manager: RiskStateManager | None = None


def get_risk_manager(state_file: Path | str = ".risk_state.json") -> RiskStateManager:
    """Get or create global risk state manager."""
    global _global_manager
    if _global_manager is None:
        _global_manager = RiskStateManager(state_file)
    return _global_manager
