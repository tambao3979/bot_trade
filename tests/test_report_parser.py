"""
Regression tests for report parser against real baseline data.
These tests validate Gate R (measurement reliability) requirements.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest


@pytest.fixture
def baseline_zip_data():
    """Real baseline data structure from phase3_behavior_baseline-2026-08-29_09-27-54.zip"""
    return {
        "strategy": {
            "TrendPullback": {
                "total_trades": 989,
                "trade_count_long": 492,
                "trade_count_short": 497,
                "profit_factor": 1.0524116935018655,
                "profit_total": 0.14018639136000008,
                "profit_total_abs": 140.18639136000007,
                "profit_total_long": -0.17843138672000002,
                "profit_total_long_abs": -178.43138672000002,
                "profit_total_short": 0.31857325288,
                "profit_total_short_abs": 318.57325288,
                "max_drawdown_account": 0.2386427203620692,
                "max_drawdown_abs": 353.0632403099997,
                "backtest_start": "2024-01-21 20:00:00",
                "backtest_end": "2026-08-28 00:00:00",
                "backtest_days": 949,
                "sharpe": 0.4780104317668131,
                "sortino": 0.6491932043606859,
                "calmar": 0.5038030076717027,
                "expectancy": 0.1417455928816982,
                "expectancy_ratio": 0.02225774648208656,
                "strategy_name": "TrendPullback",
                "stake_currency": "USDT",
                "timeframe": "15m",
                "timerange": "20240101-20260828",
                "starting_balance": 1000.0,
                "final_balance": 1140.18639136,
                "wins": 502,
                "draws": 0,
                "losses": 487,
                "winrate": 0.5076844287159757,
                "rejected_signals": 9423,
                "results_per_enter_tag": [
                    {
                        "key": "trend_pullback_short",
                        "trades": 497,
                        "profit_factor": 1.256811554752788,
                        "profit_total_pct": 31.86,
                        "profit_total": 0.31857325288,
                        "winrate": 0.6116700201207244,
                    },
                    {
                        "key": "trend_pullback_long",
                        "trades": 492,
                        "profit_factor": 0.8755631394049708,
                        "profit_total_pct": -17.84,
                        "profit_total": -0.17843138672000002,
                        "winrate": 0.4024390243902439,
                    },
                ],
                "results_per_pair": [
                    {"key": "LINK/USDT:USDT", "trades": 191, "profit_factor": 1.306329944873461},
                    {"key": "BTC/USDT:USDT", "trades": 203, "profit_factor": 0.9605849582172702},
                    {"key": "ETH/USDT:USDT", "trades": 201, "profit_factor": 1.1358306188925081},
                    {"key": "SOL/USDT:USDT", "trades": 196, "profit_factor": 1.0014204545454546},
                    {"key": "BNB/USDT:USDT", "trades": 198, "profit_factor": 1.057142857142857},
                ],
            }
        }
    }


def test_baseline_regression_total_metrics(tmp_path, baseline_zip_data):
    """Regression test: verify baseline matches plan-documented numbers."""
    from tools.report import load_backtest_summary, parse_to_metrics

    archive = tmp_path / "baseline.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("backtest.json", json.dumps(baseline_zip_data))

    raw_data = load_backtest_summary(archive, "TrendPullback")
    metrics = parse_to_metrics(raw_data, "baseline.zip", "test_sha256")

    # Gate R requirement: exact matches within tolerance 1e-8 for ratio, 1e-4 for percent
    assert metrics.total_trades == 989
    assert metrics.trade_count_long == 492
    assert metrics.trade_count_short == 497
    assert abs(metrics.profit_factor - 1.0524116935) < 1e-8
    assert abs(metrics.return_ratio - 0.1401863914) < 1e-8
    assert abs(metrics.return_pct - 14.0186) < 1e-4
    assert abs(metrics.max_drawdown_account_ratio - 0.2386427204) < 1e-8
    assert abs(metrics.max_drawdown_account_pct - 23.8643) < 1e-4
    assert abs(metrics.sharpe - 0.478010432) < 1e-8


def test_baseline_regression_long_short_breakdown(tmp_path, baseline_zip_data):
    """Verify long/short breakdown matches plan numbers."""
    from tools.report import load_backtest_summary, parse_to_metrics

    archive = tmp_path / "baseline.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("backtest.json", json.dumps(baseline_zip_data))

    raw_data = load_backtest_summary(archive, "TrendPullback")
    metrics = parse_to_metrics(raw_data, "baseline.zip", "test_sha256")

    # Long side: 492 trades, PF 0.8756, return -17.84%
    assert metrics.trade_count_long == 492
    assert abs(metrics.profit_total_long_ratio - (-0.1784)) < 1e-4
    assert abs(metrics.profit_total_long_ratio * 100 - (-17.84)) < 1e-2

    # Short side: 497 trades, PF 1.2568, return +31.86%
    assert metrics.trade_count_short == 497
    assert abs(metrics.profit_total_short_ratio - 0.3186) < 1e-4
    assert abs(metrics.profit_total_short_ratio * 100 - 31.86) < 1e-2


def test_baseline_regression_trades_per_day(tmp_path, baseline_zip_data):
    """Verify trades/day calculation matches plan."""
    from tools.report import load_backtest_summary, parse_to_metrics

    archive = tmp_path / "baseline.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("backtest.json", json.dumps(baseline_zip_data))

    raw_data = load_backtest_summary(archive, "TrendPullback")
    metrics = parse_to_metrics(raw_data, "baseline.zip", "test_sha256")

    expected_trades_per_day = 989 / 949
    assert abs(metrics.trades_per_day - expected_trades_per_day) < 1e-6
    assert abs(metrics.trades_per_day - 1.04) < 0.01


def test_parser_rejects_missing_required_fields(tmp_path):
    """Gate R requirement: parser must reject invalid data with clear error."""
    from tools.report import load_backtest_summary, parse_to_metrics

    archive = tmp_path / "invalid.zip"
    invalid_data = {
        "strategy": {
            "TestStrategy": {
                "total_trades": 100,
                # Missing trade_count_long, trade_count_short, etc.
            }
        }
    }
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("backtest.json", json.dumps(invalid_data))

    raw_data = load_backtest_summary(archive, "TestStrategy")

    with pytest.raises(ValueError, match="Missing required fields"):
        parse_to_metrics(raw_data, "invalid.zip", "test_sha256")


def test_parser_handles_zero_trades(tmp_path):
    """Gate R requirement: handle edge case of zero trades."""
    from tools.report import load_backtest_summary, parse_to_metrics

    archive = tmp_path / "zero_trades.zip"
    zero_data = {
        "strategy": {
            "TestStrategy": {
                "total_trades": 0,
                "trade_count_long": 0,
                "trade_count_short": 0,
                "profit_factor": 0.0,
                "profit_total": 0.0,
                "profit_total_abs": 0.0,
                "max_drawdown_account": 0.0,
                "max_drawdown_abs": 0.0,
                "backtest_start": "2024-01-01",
                "backtest_end": "2024-12-31",
                "backtest_days": 365,
                "strategy_name": "TestStrategy",
                "stake_currency": "USDT",
                "starting_balance": 1000.0,
                "final_balance": 1000.0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "winrate": 0.0,
            }
        }
    }
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("backtest.json", json.dumps(zero_data))

    raw_data = load_backtest_summary(archive, "TestStrategy")
    metrics = parse_to_metrics(raw_data, "zero_trades.zip", "test_sha256")

    assert metrics.total_trades == 0
    assert metrics.trades_per_day == 0.0
    assert metrics.profit_factor == 0.0


def test_parser_validates_negative_trades(tmp_path):
    """Gate R requirement: reject invalid negative trade counts."""
    from tools.report import load_backtest_summary, parse_to_metrics

    archive = tmp_path / "invalid_trades.zip"
    invalid_data = {
        "strategy": {
            "TestStrategy": {
                "total_trades": -10,  # Invalid
                "trade_count_long": 0,
                "trade_count_short": 0,
                "profit_factor": 1.0,
                "profit_total": 0.0,
                "profit_total_abs": 0.0,
                "max_drawdown_account": 0.0,
                "max_drawdown_abs": 0.0,
                "backtest_start": "2024-01-01",
                "backtest_end": "2024-12-31",
                "backtest_days": 365,
                "strategy_name": "TestStrategy",
                "stake_currency": "USDT",
                "starting_balance": 1000.0,
                "final_balance": 1000.0,
            }
        }
    }
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("backtest.json", json.dumps(invalid_data))

    raw_data = load_backtest_summary(archive, "TestStrategy")

    with pytest.raises(ValueError, match="Invalid total_trades"):
        parse_to_metrics(raw_data, "invalid_trades.zip", "test_sha256")


def test_report_output_includes_provenance(tmp_path, baseline_zip_data):
    """Gate R requirement: report must include source SHA256 and provenance."""
    from tools.report import load_backtest_summary, parse_to_metrics, render_summary

    archive = tmp_path / "baseline.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("backtest.json", json.dumps(baseline_zip_data))

    raw_data = load_backtest_summary(archive, "TrendPullback")
    metrics = parse_to_metrics(raw_data, "baseline.zip", "abc123def456")

    report = render_summary(metrics)

    assert "abc123def456" in report
    assert "baseline.zip" in report
    assert "TrendPullback" in report
    assert "Provenance" in report


def test_report_breakdown_includes_tag_and_pair(tmp_path, baseline_zip_data):
    """Gate R requirement: report must include per-tag and per-pair breakdowns."""
    from tools.report import load_backtest_summary, parse_to_metrics, render_summary

    archive = tmp_path / "baseline.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("backtest.json", json.dumps(baseline_zip_data))

    raw_data = load_backtest_summary(archive, "TrendPullback")
    metrics = parse_to_metrics(raw_data, "baseline.zip", "test_sha256")

    assert metrics.results_per_enter_tag is not None
    assert len(metrics.results_per_enter_tag) == 2
    assert metrics.results_per_pair is not None
    assert len(metrics.results_per_pair) == 5

    report = render_summary(metrics)
    assert "Per-Tag Performance" in report
    assert "Per-Pair Performance" in report
    assert "trend_pullback_short" in report
    assert "trend_pullback_long" in report
    assert "LINK/USDT:USDT" in report


def test_report_units_are_explicit(tmp_path, baseline_zip_data):
    """Gate R requirement: units must be explicit (ratio vs percent vs stake)."""
    from tools.report import load_backtest_summary, parse_to_metrics, render_summary

    archive = tmp_path / "baseline.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("backtest.json", json.dumps(baseline_zip_data))

    raw_data = load_backtest_summary(archive, "TrendPullback")
    metrics = parse_to_metrics(raw_data, "baseline.zip", "test_sha256")

    report = render_summary(metrics)

    # Check that report shows both ratio and percent for clarity
    assert "ratio:" in report.lower()
    assert "%" in report
    assert "USDT" in report  # stake currency explicit


def test_cli_returns_nonzero_on_missing_mode(tmp_path):
    """Gate R requirement: CLI must return non-zero exit code when mode missing."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "tools.report", "--strategy", "Test"],
        capture_output=True,
        cwd=Path(__file__).parent.parent,
    )

    # Should fail because neither --results nor --baseline/--candidate provided
    assert result.returncode != 0
    assert b"Error:" in result.stderr or b"required" in result.stderr.lower()
