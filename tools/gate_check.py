#!/usr/bin/env python3
"""Gate Q screening checker for candidates.

Validates candidate against all Gate Q criteria from EXPERIMENT_SPEC.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_metrics(report_path: Path) -> dict[str, Any]:
    """Load metrics from backtest result ZIP or report JSON."""
    if report_path.suffix == ".zip":
        # Use report tool to parse
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "tools.report", str(report_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise ValueError(f"Report tool failed: {result.stderr}")

        # Parse output to extract metrics
        # This is simplified - actual implementation would parse structured output
        raise NotImplementedError("ZIP parsing not yet implemented")

    elif report_path.suffix == ".json":
        with open(report_path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        raise ValueError(f"Unsupported file type: {report_path.suffix}")


def check_full_period_gate(metrics: dict[str, Any]) -> tuple[bool, list[str]]:
    """Check full period Gate Q criteria."""
    failures = []

    trades = metrics.get("total_trades", 0)
    pf = metrics.get("profit_factor", 0)
    return_pct = metrics.get("return_pct", 0)
    expectancy = metrics.get("expectancy", 0)
    max_dd_pct = metrics.get("max_drawdown_pct", 100)
    sharpe = metrics.get("sharpe_daily", 0)

    if trades < 450:
        failures.append(f"Trades {trades} < 450")
    if pf < 1.15:
        failures.append(f"PF {pf:.4f} < 1.15")
    if return_pct <= 0:
        failures.append(f"Return {return_pct:.2f}% <= 0")
    if expectancy <= 0:
        failures.append(f"Expectancy {expectancy:.4f} <= 0")
    if max_dd_pct > 15:
        failures.append(f"Max DD {max_dd_pct:.2f}% > 15%")
    if sharpe < 0.75:
        failures.append(f"Daily Sharpe {sharpe:.3f} < 0.75")

    return len(failures) == 0, failures


def check_recent_gate(metrics: dict[str, Any]) -> tuple[bool, list[str]]:
    """Check recent period (2026) Gate Q criteria."""
    failures = []

    trades = metrics.get("total_trades", 0)
    pf = metrics.get("profit_factor", 0)
    return_pct = metrics.get("return_pct", 0)
    max_dd_pct = metrics.get("max_drawdown_pct", 100)

    if trades < 100:
        failures.append(f"Trades {trades} < 100")
    if pf < 1.10:
        failures.append(f"PF {pf:.4f} < 1.10")
    if return_pct <= 0:
        failures.append(f"Return {return_pct:.2f}% <= 0")
    if max_dd_pct > 12:
        failures.append(f"Max DD {max_dd_pct:.2f}% > 12%")

    return len(failures) == 0, failures


def check_side_gate(metrics: dict[str, Any]) -> tuple[bool, list[str]]:
    """Check side robustness criteria."""
    failures = []

    long_trades = metrics.get("long_trades", 0)
    short_trades = metrics.get("short_trades", 0)
    long_pf = metrics.get("long_pf", 0)
    short_pf = metrics.get("short_pf", 0)

    # Check each active side (>0 trades)
    if long_trades > 0:
        if long_trades < 100:
            failures.append(f"Long trades {long_trades} < 100")
        if long_pf < 1.05:
            failures.append(f"Long PF {long_pf:.4f} < 1.05")

    if short_trades > 0:
        if short_trades < 100:
            failures.append(f"Short trades {short_trades} < 100")
        if short_pf < 1.05:
            failures.append(f"Short PF {short_pf:.4f} < 1.05")

    return len(failures) == 0, failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Gate Q screening criteria")
    parser.add_argument("full_period", type=Path, help="Full period backtest result")
    parser.add_argument("--recent", type=Path, help="Recent period (2026) backtest result")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # This is a placeholder - full implementation would parse actual backtest results
    print("Gate Q Screening Check")
    print("=" * 60)
    print()
    print("NOTE: This is a screening tool stub.")
    print("Full implementation requires parsing backtest ZIPs.")
    print()
    print("Manual screening steps:")
    print("1. Run: python -m tools.report <backtest.zip>")
    print("2. Check metrics against EXPERIMENT_SPEC.md Gate Q criteria")
    print("3. Document pass/fail in PROGRESS.md")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
