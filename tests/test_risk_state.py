"""Tests for persistent risk state management."""

import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from user_data.strategies.lib.risk_state import RiskState, RiskStateManager


class TestRiskState:
    def test_state_serialization(self):
        state = RiskState(
            daily_realized_pnl=-50.0,
            daily_start_equity=1000.0,
            daily_reset_date="2026-08-29",
            halt_active=True,
            halt_reason="daily_loss",
        )

        data = state.to_dict()
        loaded = RiskState.from_dict(data)

        assert loaded.daily_realized_pnl == -50.0
        assert loaded.daily_start_equity == 1000.0
        assert loaded.halt_active is True
        assert loaded.halt_reason == "daily_loss"

    def test_state_rejects_unsupported_schema(self):
        data = {"schema_version": 999}
        with pytest.raises(ValueError, match="Unsupported schema version"):
            RiskState.from_dict(data)


class TestRiskStateManager:
    def test_manager_creates_new_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "risk_state.json"
            manager = RiskStateManager(state_file)

            state = manager.get_state()
            assert state.daily_realized_pnl == 0.0
            assert state.halt_active is False

    def test_manager_loads_existing_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "risk_state.json"

            # Create initial state
            manager1 = RiskStateManager(state_file)
            manager1._state.daily_realized_pnl = -100.0
            manager1._state.peak_equity = 5000.0
            manager1._save()

            # Load in new manager
            manager2 = RiskStateManager(state_file)
            state = manager2.get_state()
            assert state.daily_realized_pnl == -100.0
            assert state.peak_equity == 5000.0

    def test_manager_handles_corrupted_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "risk_state.json"

            # Write invalid JSON
            state_file.write_text("{invalid json", encoding="utf-8")

            manager = RiskStateManager(state_file)
            state = manager.get_state()

            # Should be halted due to corruption
            assert state.halt_active is True
            assert "state_corruption" in state.halt_reason

    def test_daily_reset_on_date_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "risk_state.json"
            manager = RiskStateManager(state_file)

            # Set initial state
            day1 = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
            manager.update_equity(1000.0, day1)
            manager.record_trade_pnl(-50.0, day1)

            assert manager._state.daily_realized_pnl == -50.0

            # Move to next day
            day2 = datetime(2026, 8, 30, 1, 0, tzinfo=UTC)
            reset = manager.check_daily_reset(day2)

            assert reset is True
            assert manager._state.daily_realized_pnl == 0.0
            assert manager._state.daily_start_equity is None

    def test_weekly_reset_on_monday(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "risk_state.json"
            manager = RiskStateManager(state_file)

            # Friday Aug 29, 2026
            friday = datetime(2026, 8, 29, 12, 0, tzinfo=UTC)
            manager.update_equity(1000.0, friday)
            manager.record_trade_pnl(-100.0, friday)

            assert manager._state.weekly_realized_pnl == -100.0

            # Monday Sep 1, 2026 (new week)
            monday = datetime(2026, 9, 1, 1, 0, tzinfo=UTC)
            reset = manager.check_weekly_reset(monday)

            assert reset is True
            assert manager._state.weekly_realized_pnl == 0.0

    def test_peak_equity_tracking(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "risk_state.json"
            manager = RiskStateManager(state_file)

            now = datetime.now(UTC)

            manager.update_equity(1000.0, now)
            assert manager._state.peak_equity == 1000.0

            manager.update_equity(1200.0, now)
            assert manager._state.peak_equity == 1200.0

            # Lower equity doesn't update peak
            manager.update_equity(1100.0, now)
            assert manager._state.peak_equity == 1200.0

    def test_daily_loss_limit_triggers_halt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "risk_state.json"
            manager = RiskStateManager(state_file)

            now = datetime.now(UTC)
            manager.update_equity(1000.0, now)
            manager.record_trade_pnl(-25.0, now)  # -2.5% loss

            # Should halt at 2% loss
            halted = manager.check_daily_loss_limit(2.0, now)
            assert halted is True
            assert manager.is_halted()
            assert "daily_loss" in manager.get_halt_reason()

    def test_weekly_loss_limit_triggers_halt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "risk_state.json"
            manager = RiskStateManager(state_file)

            now = datetime.now(UTC)
            manager.update_equity(1000.0, now)
            manager.record_trade_pnl(-60.0, now)  # -6% loss

            # Should halt at 5% weekly loss
            halted = manager.check_weekly_loss_limit(5.0, now)
            assert halted is True
            assert manager.is_halted()
            assert "weekly_loss" in manager.get_halt_reason()

    def test_drawdown_limit_triggers_halt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "risk_state.json"
            manager = RiskStateManager(state_file)

            now = datetime.now(UTC)
            manager.update_equity(1000.0, now)  # Peak = 1000

            # Drop to 850 = 15% drawdown
            halted = manager.check_drawdown_limit(850.0, 10.0, now)
            assert halted is True
            assert manager.is_halted()
            assert "drawdown" in manager.get_halt_reason()

    def test_halt_persists_across_restarts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "risk_state.json"

            # First manager: trigger halt
            manager1 = RiskStateManager(state_file)
            now = datetime.now(UTC)
            manager1.set_halt("test_reason", now)
            assert manager1.is_halted()

            # Second manager: halt should still be active
            manager2 = RiskStateManager(state_file)
            assert manager2.is_halted()
            assert manager2.get_halt_reason() == "test_reason"

    def test_clear_halt_requires_manual_action(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "risk_state.json"
            manager = RiskStateManager(state_file)

            now = datetime.now(UTC)
            manager.set_halt("test", now)
            assert manager.is_halted()

            # Halt doesn't clear automatically
            manager.check_daily_reset(now + timedelta(days=1))
            assert manager.is_halted()

            # Must clear manually
            manager.clear_halt()
            assert not manager.is_halted()

    def test_atomic_write_with_temp_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "risk_state.json"
            manager = RiskStateManager(state_file)

            now = datetime.now(UTC)
            manager.update_equity(1000.0, now)

            # State file should exist
            assert state_file.exists()

            # Should be valid JSON
            with open(state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            assert "peak_equity" in data
            assert data["peak_equity"] == 1000.0

            # No temp files should remain
            temp_files = list(Path(tmpdir).glob(".risk_state_tmp_*"))
            assert len(temp_files) == 0

    def test_no_halt_when_below_limits(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "risk_state.json"
            manager = RiskStateManager(state_file)

            now = datetime.now(UTC)
            manager.update_equity(1000.0, now)
            manager.record_trade_pnl(-10.0, now)  # -1% loss

            # Should NOT halt at 2% limit
            halted_daily = manager.check_daily_loss_limit(2.0, now)
            halted_weekly = manager.check_weekly_loss_limit(5.0, now)
            halted_dd = manager.check_drawdown_limit(990.0, 10.0, now)

            assert halted_daily is False
            assert halted_weekly is False
            assert halted_dd is False
            assert not manager.is_halted()
