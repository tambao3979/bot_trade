"""Fast local validation for the walk-forward and Monte Carlo utilities."""

from __future__ import annotations

import json
import zipfile

import numpy as np
import pytest

from tools.montecarlo import compute_drawdown
from tools.walkforward import (
    add_months,
    compute_metrics_from_trades,
    freqtrade_binary,
    infer_hyperopt_spaces,
    load_backtest_export,
    parse_timerange,
    run_hyperopt,
)


def test_walkforward_date_helpers_handle_month_end() -> None:
    assert parse_timerange("20200101-20240101") == ("20200101", "20240101")
    assert add_months("20240131", 1) == "20240229"


def test_walkforward_uses_the_active_virtual_environment_cli() -> None:
    assert freqtrade_binary().endswith("freqtrade.exe")


def test_walkforward_infers_only_declared_hyperopt_spaces() -> None:
    assert infer_hyperopt_spaces("TrendPullback") == ["buy"]
    assert infer_hyperopt_spaces("MetaRouter") == []


def test_walkforward_rejects_an_invalid_hyperopt_worker_count(tmp_path) -> None:
    from pathlib import Path
    with pytest.raises(ValueError, match="workers"):
        run_hyperopt("TrendPullback", "config.json", "20240101-20240201", fold_dir=Path(tmp_path), workers=0)


def test_walkforward_reads_current_freqtrade_export_format(tmp_path) -> None:
    archive = tmp_path / "backtest.zip"
    payload = {"strategy": {"Demo": {"trades": [{"profit_ratio": 0.01}]}}}
    with zipfile.ZipFile(archive, "w") as exported:
        exported.writestr("backtest.json", json.dumps(payload))
        exported.writestr("backtest_config.json", "{}")
        exported.writestr("backtest_Demo.json", json.dumps({"strategy_name": "Demo"}))

    assert load_backtest_export(archive, "Demo")["trades"] == [{"profit_ratio": 0.01}]


def test_walkforward_metrics_discard_non_finite_trade_values() -> None:
    metrics = compute_metrics_from_trades(
        [{"profit_ratio": 0.10}, {"profit_ratio": -0.05}, {"profit_ratio": float("nan")}]
    )
    assert metrics["trade_count"] == 2
    assert np.isfinite(metrics["profit_factor"])


def test_montecarlo_drawdown_handles_zero_equity() -> None:
    assert compute_drawdown(np.array([1.0, 0.0, 0.0])) == 1.0
    assert compute_drawdown(np.array([np.nan])) == 0.0


def test_report_resolves_zip_directly(tmp_path) -> None:
    from tools.report import resolve_result_archive

    archive = tmp_path / "backtest.zip"
    archive.touch()
    assert resolve_result_archive(archive) == archive


def test_report_resolves_directory_with_last_result(tmp_path) -> None:
    from tools.report import resolve_result_archive

    archive = tmp_path / "backtest-2026-08-28.zip"
    archive.touch()
    last_result = tmp_path / ".last_result.json"
    last_result.write_text(json.dumps({"latest_backtest": "backtest-2026-08-28.zip"}))
    assert resolve_result_archive(tmp_path) == archive


def test_report_resolves_directory_fallback_newest_zip(tmp_path) -> None:
    import time

    from tools.report import resolve_result_archive

    old_archive = tmp_path / "backtest-old.zip"
    old_archive.touch()
    time.sleep(0.01)
    new_archive = tmp_path / "backtest-new.zip"
    new_archive.touch()
    assert resolve_result_archive(tmp_path) == new_archive


def test_report_loads_strategy_from_archive(tmp_path) -> None:
    from tools.report import load_backtest_summary

    archive = tmp_path / "backtest.zip"
    # Schema: Freqtrade 2026.7 format
    payload = {
        "strategy": {
            "TrendPullback": {
                "total_trades": 989,
                "trade_count_long": 492,
                "trade_count_short": 497,
                "profit_factor": 1.0524,
                "profit_total": 0.1402,  # ratio, not percent
                "profit_total_abs": 140.2,
                "max_drawdown_account": 0.2386,  # ratio
                "max_drawdown_abs": 353.06,
                "backtest_start": "2024-01-01",
                "backtest_end": "2026-08-28",
                "backtest_days": 949,
                "strategy_name": "TrendPullback",
                "stake_currency": "USDT",
                "starting_balance": 1000.0,
                "final_balance": 1140.2,
            }
        }
    }
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("backtest.json", json.dumps(payload))

    summary = load_backtest_summary(archive, "TrendPullback")
    assert summary["total_trades"] == 989
    assert summary["profit_factor"] == 1.0524
    assert summary["trade_count_long"] == 492
    assert summary["trade_count_short"] == 497


def test_report_rejects_missing_strategy(tmp_path) -> None:
    from tools.report import load_backtest_summary

    archive = tmp_path / "backtest.zip"
    payload = {"strategy": {"OtherStrategy": {}}}
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("backtest.json", json.dumps(payload))

    with pytest.raises(ValueError, match="TrendPullback"):
        load_backtest_summary(archive, "TrendPullback")


def test_report_renders_summary_with_metrics(tmp_path) -> None:
    from tools.report import BacktestMetrics, render_summary

    metrics = BacktestMetrics(
        source_file="test.zip",
        source_sha256="a" * 64,
        strategy_name="TestStrategy",
        generated_at="2026-08-29T00:00:00Z",
        backtest_start="2024-01-01",
        backtest_end="2026-08-28",
        backtest_days=950,
        timerange="20240101-20260828",
        timeframe="15m",
        total_trades=989,
        trade_count_long=492,
        trade_count_short=497,
        trades_per_day=1.04,
        return_ratio=0.1402,
        return_pct=14.02,
        return_abs_stake=140.2,
        profit_total_long_ratio=-0.10,
        profit_total_long_abs=-100.0,
        profit_total_short_ratio=0.24,
        profit_total_short_abs=240.2,
        profit_factor=1.0524,
        expectancy=0.05,
        expectancy_ratio=0.02,
        sharpe=0.4780,
        sortino=0.65,
        calmar=0.50,
        max_drawdown_account_ratio=0.2386,
        max_drawdown_account_pct=23.86,
        max_drawdown_abs_stake=353.06,
        wins=500,
        draws=0,
        losses=489,
        winrate=0.505,
        rejected_signals=237,
        stake_currency="USDT",
        starting_balance=1000.0,
        final_balance=1140.2,
    )
    report = render_summary(metrics)
    assert "989" in report
    assert "1.0524" in report
    assert "23.86" in report
    assert "492" in report  # long trades
    assert "497" in report  # short trades


def test_report_comparison_shows_deltas(tmp_path) -> None:
    from tools.report import BacktestMetrics, render_comparison

    baseline = BacktestMetrics(
        source_file="baseline.zip",
        source_sha256="b" * 64,
        strategy_name="TestStrategy",
        generated_at="2026-08-29T00:00:00Z",
        backtest_start="2024-01-01",
        backtest_end="2026-08-28",
        backtest_days=950,
        timerange="20240101-20260828",
        timeframe="15m",
        total_trades=989,
        trade_count_long=492,
        trade_count_short=497,
        trades_per_day=1.04,
        return_ratio=0.1402,
        return_pct=14.02,
        return_abs_stake=140.2,
        profit_total_long_ratio=0.0,
        profit_total_long_abs=0.0,
        profit_total_short_ratio=0.0,
        profit_total_short_abs=0.0,
        profit_factor=1.0524,
        expectancy=0.05,
        expectancy_ratio=0.02,
        sharpe=0.4780,
        sortino=0.65,
        calmar=0.50,
        max_drawdown_account_ratio=0.2386,
        max_drawdown_account_pct=23.86,
        max_drawdown_abs_stake=353.06,
        wins=500,
        draws=0,
        losses=489,
        winrate=0.505,
        rejected_signals=237,
        stake_currency="USDT",
        starting_balance=1000.0,
        final_balance=1140.2,
    )

    candidate = BacktestMetrics(
        source_file="candidate.zip",
        source_sha256="c" * 64,
        strategy_name="TestStrategy",
        generated_at="2026-08-29T00:00:00Z",
        backtest_start="2024-01-01",
        backtest_end="2026-08-28",
        backtest_days=950,
        timerange="20240101-20260828",
        timeframe="15m",
        total_trades=1187,
        trade_count_long=600,
        trade_count_short=587,
        trades_per_day=1.25,
        return_ratio=0.16,
        return_pct=16.0,
        return_abs_stake=160.0,
        profit_total_long_ratio=0.0,
        profit_total_long_abs=0.0,
        profit_total_short_ratio=0.0,
        profit_total_short_abs=0.0,
        profit_factor=1.08,
        expectancy=0.06,
        expectancy_ratio=0.03,
        sharpe=0.55,
        sortino=0.75,
        calmar=0.60,
        max_drawdown_account_ratio=0.20,
        max_drawdown_account_pct=20.0,
        max_drawdown_abs_stake=300.0,
        wins=620,
        draws=0,
        losses=567,
        winrate=0.522,
        rejected_signals=250,
        stake_currency="USDT",
        starting_balance=1000.0,
        final_balance=1160.0,
    )

    report = render_comparison(baseline, candidate)
    assert "989" in report
    assert "1187" in report
    assert "Delta" in report
    assert "+" in report  # positive deltas
