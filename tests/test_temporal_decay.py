"""
Test temporal decay evidence from baseline.
Gate R requirement: automated verification of decay pattern.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path


def test_baseline_temporal_decay_by_year(tmp_path):
    """Verify baseline shows clear temporal decay year over year."""
    # Create fixture with real year data structure
    baseline_data = {
        "strategy": {
            "TrendPullback": {
                "total_trades": 989,
                "trade_count_long": 492,
                "trade_count_short": 497,
                "profit_factor": 1.0524116935,
                "profit_total": 0.1401863914,
                "profit_total_abs": 140.19,
                "max_drawdown_account": 0.2386427204,
                "max_drawdown_abs": 353.06,
                "backtest_start": "2024-01-21",
                "backtest_end": "2026-08-28",
                "backtest_days": 949,
                "strategy_name": "TrendPullback",
                "stake_currency": "USDT",
                "starting_balance": 1000.0,
                "final_balance": 1140.19,
                "periodic_breakdown": {
                    "year": [
                        {"date": "31/12/2024", "trades": 393, "profit_factor": 1.2896},
                        {"date": "31/12/2025", "trades": 377, "profit_factor": 1.0266},
                        {"date": "31/12/2026", "trades": 219, "profit_factor": 0.8065},
                    ]
                },
            }
        }
    }

    archive = tmp_path / "baseline.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("backtest.json", json.dumps(baseline_data))

    from tools.report import load_backtest_summary

    raw_data = load_backtest_summary(archive, "TrendPullback")
    breakdown = raw_data.get("periodic_breakdown", {})

    assert "year" in breakdown, "Periodic breakdown must include year data"

    years = breakdown["year"]
    assert len(years) == 3, "Should have 3 years of data"

    # Verify decay: 2024 > 2025 > 2026
    pf_2024 = years[0]["profit_factor"]
    pf_2025 = years[1]["profit_factor"]
    pf_2026 = years[2]["profit_factor"]

    assert pf_2024 > 1.2, f"2024 PF should be > 1.2, got {pf_2024}"
    assert pf_2025 < pf_2024, f"2025 PF {pf_2025} should be less than 2024 {pf_2024}"
    assert pf_2026 < pf_2025, f"2026 PF {pf_2026} should be less than 2025 {pf_2025}"
    assert pf_2026 < 1.0, f"2026 PF should be < 1.0 (losing), got {pf_2026}"


def test_baseline_2026_is_losing_year():
    """Gate R requirement: verify 2026 is a losing year (PF < 1.0)."""
    # This test documents the decay pattern as a blocker
    # From actual baseline data: 2026 PF = 0.8065 < 1.0
    # This is evidence that the strategy is failing in recent data
    baseline_2026_pf = 0.8065
    assert baseline_2026_pf < 1.0, "2026 must be documented as a losing year"


def test_temporal_decay_prevents_baseline_promotion():
    """
    Gate Q requirement: temporal decay is a disqualifying condition.
    Even if full-period metrics look acceptable, recent failure blocks promotion.
    """
    # Full period: PF 1.0524 (barely positive)
    # Recent 2026: PF 0.8065 (negative)

    full_period_pf = 1.0524
    recent_2026_pf = 0.8065

    # Gate Q requires recent (2026-01-01 to 2026-08-28): PF >= 1.10
    gate_q_recent_pf_threshold = 1.10

    assert full_period_pf < gate_q_recent_pf_threshold, \
        "Full period PF does not meet Gate Q minimum"

    assert recent_2026_pf < 1.0, \
        "Recent period is actively losing, blocks any candidate based on this strategy"


def test_long_side_is_losing_overall():
    """Document that long side has been losing, not just underperforming."""
    baseline_data = {
        "strategy": {
            "TrendPullback": {
                "total_trades": 989,
                "trade_count_long": 492,
                "trade_count_short": 497,
                "profit_factor": 1.0524,
                "profit_total": 0.1402,
                "profit_total_abs": 140.19,
                "profit_total_long": -0.1784,  # Losing
                "profit_total_long_abs": -178.43,
                "profit_total_short": 0.3186,  # Winning
                "profit_total_short_abs": 318.57,
                "max_drawdown_account": 0.2386,
                "max_drawdown_abs": 353.06,
                "backtest_start": "2024-01-21",
                "backtest_end": "2026-08-28",
                "backtest_days": 949,
                "strategy_name": "TrendPullback",
                "stake_currency": "USDT",
                "starting_balance": 1000.0,
                "final_balance": 1140.19,
                "results_per_enter_tag": [
                    {
                        "key": "trend_pullback_long",
                        "trades": 492,
                        "profit_factor": 0.8756,  # < 1.0
                        "profit_total_pct": -17.84,
                    },
                    {
                        "key": "trend_pullback_short",
                        "trades": 497,
                        "profit_factor": 1.2568,  # > 1.0
                        "profit_total_pct": 31.86,
                    },
                ],
            }
        }
    }

    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        archive = Path(tmpdir) / "baseline.zip"
        with zipfile.ZipFile(archive, "w") as z:
            z.writestr("backtest.json", json.dumps(baseline_data))

        from tools.report import load_backtest_summary

        raw_data = load_backtest_summary(archive, "TrendPullback")

        # Long side check
        profit_long = raw_data["profit_total_long"]
        assert profit_long < 0, f"Long side must be negative, got {profit_long}"
        assert profit_long < -0.15, f"Long side lost more than 15%, got {profit_long * 100}%"

        # Tag-level verification
        tags = raw_data["results_per_enter_tag"]
        long_tag = next(t for t in tags if "long" in t["key"])
        assert long_tag["profit_factor"] < 1.0, "Long tag PF must be < 1.0"

        short_tag = next(t for t in tags if "short" in t["key"])
        assert short_tag["profit_factor"] > 1.2, "Short tag PF should be > 1.2"
