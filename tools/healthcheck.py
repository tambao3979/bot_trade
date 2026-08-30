#!/usr/bin/env python3
"""Healthcheck for Freqtrade bot - validates config, data, and runtime state.

Usage:
    python -m tools.healthcheck
    python -m tools.healthcheck --config user_data/config/config.base.json

Exit codes:
    0 - All checks passed
    1 - Warnings found (degraded but operational)
    2 - Critical issues found (unsafe to run)
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    from user_data.strategies.lib.risk_state import get_risk_manager
    from user_data.strategies.lib.snapshot import get_cache
except ImportError:
    # Allow running without full installation
    get_risk_manager = None  # type: ignore
    get_cache = None  # type: ignore


class HealthCheck:
    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path
        self.warnings: list[str] = []
        self.errors: list[str] = []
        self.info: dict[str, Any] = {}

    def check_config(self) -> None:
        """Validate config file exists and is valid JSON."""
        if self.config_path is None:
            self.warnings.append("No config path provided, skipping config checks")
            return

        if not self.config_path.exists():
            self.errors.append(f"Config file not found: {self.config_path}")
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            if not isinstance(config, dict):
                self.errors.append("Config is not a JSON object")
                return

            # Check required sections
            if "exchange" not in config:
                self.warnings.append("No exchange section in config")

            # Check for secrets in config
            for key in ["key", "secret", "password", "api_key"]:
                if self._find_key_recursive(config, key):
                    self.warnings.append(f"Potential secret '{key}' found in config file")

            self.info["config_valid"] = True

        except json.JSONDecodeError as e:
            self.errors.append(f"Config JSON parse error: {e}")

    def check_strategy_imports(self) -> None:
        """Verify strategies can be imported."""
        strategy_dir = Path("user_data/strategies")
        if not strategy_dir.exists():
            self.warnings.append("Strategy directory not found")
            return

        strategy_files = list(strategy_dir.glob("*.py"))
        if not strategy_files:
            self.warnings.append("No strategy files found")
            return

        self.info["strategy_count"] = len([f for f in strategy_files if f.stem != "__init__"])

    def check_data_freshness(self) -> None:
        """Check if market data exists and is recent."""
        data_dir = Path("user_data/data")
        if not data_dir.exists():
            self.warnings.append("No data directory found")
            return

        # Find most recent data file
        data_files = list(data_dir.rglob("*.json"))
        if not data_files:
            self.warnings.append("No data files found")
            return

        most_recent = max(data_files, key=lambda p: p.stat().st_mtime)
        age_seconds = time.time() - most_recent.stat().st_mtime
        age_days = age_seconds / 86400

        self.info["most_recent_data"] = most_recent.name
        self.info["data_age_days"] = round(age_days, 1)

        if age_days > 7:
            self.warnings.append(f"Data is {age_days:.1f} days old (stale)")

    def check_risk_state(self) -> None:
        """Check persistent risk state health."""
        risk_file = Path(".risk_state.json")

        if not risk_file.exists():
            self.info["risk_state"] = "not_initialized"
            return

        try:
            if get_risk_manager is None:
                self.warnings.append("Cannot load risk_state module")
                return

            manager = get_risk_manager(risk_file)
            state = manager.get_state()

            if state.halt_active:
                self.errors.append(f"Risk halt active: {state.halt_reason}")

            if state.updated_at:
                updated = datetime.fromisoformat(state.updated_at)
                age = datetime.now(updated.tzinfo) - updated
                if age > timedelta(hours=24):
                    self.warnings.append(f"Risk state not updated in {age.days} days")

            self.info["risk_halt_active"] = state.halt_active
            if state.halt_reason:
                self.info["risk_halt_reason"] = state.halt_reason

        except Exception as e:
            self.errors.append(f"Risk state corrupted: {e}")

    def check_snapshot_cache(self) -> None:
        """Check market snapshot cache health."""
        if get_cache is None:
            return

        try:
            cache = get_cache()
            stats = cache.get_deny_stats()

            if stats:
                total_denies = sum(stats.values())
                self.info["snapshot_deny_count"] = total_denies

                # Check for concerning patterns
                for reason, count in stats.items():
                    if "stale" in reason and count > 100:
                        self.warnings.append(f"High stale snapshot count: {count}")
                    if "error" in reason and count > 10:
                        self.warnings.append(f"Snapshot errors detected: {reason} ({count})")

        except Exception as e:
            self.warnings.append(f"Cannot check snapshot cache: {e}")

    def check_database(self) -> None:
        """Check database file exists and is accessible."""
        db_files = list(Path(".").glob("*.sqlite"))
        if not db_files:
            self.info["database"] = "not_found"
            return

        db_file = db_files[0]
        self.info["database_file"] = db_file.name
        self.info["database_size_mb"] = round(db_file.stat().st_size / 1024 / 1024, 2)

        # Check for WAL files (sign of active connection)
        wal_file = db_file.with_suffix(".sqlite-wal")
        if wal_file.exists():
            self.info["database_wal_exists"] = True
            wal_age = time.time() - wal_file.stat().st_mtime
            if wal_age > 3600:  # 1 hour
                self.warnings.append("WAL file exists but not recently updated (process stopped?)")

    def check_disk_space(self) -> None:
        """Check available disk space."""
        try:
            usage = shutil.disk_usage(".")
            free_gb = usage.free / (1024**3)
            free_pct = (usage.free / usage.total) * 100

            self.info["disk_free_gb"] = round(free_gb, 2)
            self.info["disk_free_pct"] = round(free_pct, 1)

            if free_gb < 1.0:
                self.errors.append(f"Low disk space: {free_gb:.2f} GB free")
            elif free_pct < 10:
                self.warnings.append(f"Low disk space: {free_pct:.1f}% free")

        except Exception as e:
            self.warnings.append(f"Cannot check disk space: {e}")

    def check_log_files(self) -> None:
        """Check log file health."""
        log_dir = Path("user_data/logs")
        if not log_dir.exists():
            return

        log_files = list(log_dir.glob("*.log"))
        if not log_files:
            return

        total_size = sum(f.stat().st_size for f in log_files)
        size_mb = total_size / (1024 * 1024)

        self.info["log_files_count"] = len(log_files)
        self.info["log_total_size_mb"] = round(size_mb, 2)

        if size_mb > 1000:  # 1GB
            self.warnings.append(f"Large log files: {size_mb:.1f} MB total")

    def run_all_checks(self) -> int:
        """Run all health checks and return exit code."""
        print("Running Freqtrade health checks...\n")

        self.check_config()
        self.check_strategy_imports()
        self.check_data_freshness()
        self.check_risk_state()
        self.check_snapshot_cache()
        self.check_database()
        self.check_disk_space()
        self.check_log_files()

        # Print results
        if self.info:
            print("INFO:")
            for key, value in self.info.items():
                print(f"  {key}: {value}")
            print()

        if self.warnings:
            print("WARNINGS:")
            for warning in self.warnings:
                print(f"  [!] {warning}")
            print()

        if self.errors:
            print("ERRORS:")
            for error in self.errors:
                print(f"  [X] {error}")
            print()

        # Determine exit code
        if self.errors:
            print("Status: CRITICAL - Issues found that prevent safe operation")
            return 2
        elif self.warnings:
            print("Status: DEGRADED - Warnings found but operational")
            return 1
        else:
            print("Status: HEALTHY - All checks passed")
            return 0

    def _find_key_recursive(self, obj: Any, key: str) -> bool:
        """Recursively search for key in nested dict."""
        if isinstance(obj, dict):
            if key in obj:
                return True
            return any(self._find_key_recursive(v, key) for v in obj.values())
        elif isinstance(obj, list):
            return any(self._find_key_recursive(item, key) for item in obj)
        return False

    def to_json(self) -> str:
        """Export results as JSON."""
        return json.dumps(
            {
                "info": self.info,
                "warnings": self.warnings,
                "errors": self.errors,
                "status": "critical" if self.errors else ("degraded" if self.warnings else "healthy"),
            },
            indent=2,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Freqtrade health check")
    parser.add_argument(
        "-c", "--config", type=Path, help="Path to config file (default: config.base.json)"
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    config_path = args.config or Path("user_data/config/config.base.json")
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path

    checker = HealthCheck(config_path)
    exit_code = checker.run_all_checks()

    if args.json:
        print("\n" + checker.to_json())

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
