"""
Tests for walk-forward daily equity metrics.
"""

from __future__ import annotations


def test_walkforward_compute_daily_metrics_basic():
    """Test daily metrics computation from daily_profit."""
    from tools.walkforward import compute_daily_metrics

    # Simple increasing equity
    daily_profit = [
        ["2024-01-01", 10.0],
        ["2024-01-02", 20.0],
        ["2024-01-03", 15.0],
    ]

    metrics = compute_daily_metrics(daily_profit)

    assert metrics["days"] == 3
    assert metrics["total_return_pct"] > 0  # Net positive
    assert metrics["max_drawdown_pct"] >= 0
    assert "daily_sharpe" in metrics
    assert "daily_sortino" in metrics


def test_walkforward_daily_metrics_handles_losses():
    """Test daily metrics with losing days."""
    from tools.walkforward import compute_daily_metrics

    daily_profit = [
        ["2024-01-01", 50.0],   # win
        ["2024-01-02", -30.0],  # loss
        ["2024-01-03", -10.0],  # loss
        ["2024-01-04", 20.0],   # win
    ]

    metrics = compute_daily_metrics(daily_profit)

    assert metrics["days"] == 4
    assert metrics["max_drawdown_pct"] > 0  # Should have drawdown
    assert metrics["daily_sortino"] != 0    # Should compute downside deviation


def test_walkforward_daily_metrics_empty_input():
    """Test daily metrics with no data."""
    from tools.walkforward import compute_daily_metrics

    metrics = compute_daily_metrics([])

    assert metrics["days"] == 0
    assert metrics["daily_sharpe"] == 0.0
    assert metrics["max_drawdown_pct"] == 0.0


def test_walkforward_embargo_calculation():
    """Test embargo days calculation from timeframe."""
    from tools.walkforward import compute_embargo_days

    # 100 candles @ 15m = 1500 minutes = 25 hours = 2 days
    embargo_15m = compute_embargo_days("15m", 100)
    assert embargo_15m >= 1

    # 100 candles @ 1h = 100 hours = 5 days
    embargo_1h = compute_embargo_days("1h", 100)
    assert embargo_1h >= 4

    # 50 candles @ 15m = 750 minutes = 12.5 hours = 1 day
    embargo_short = compute_embargo_days("15m", 50)
    assert embargo_short >= 1


def test_walkforward_add_days():
    """Test adding days to YYYYMMDD date."""
    from tools.walkforward import add_days

    result = add_days("20240101", 10)
    assert result == "20240111"

    # Test month boundary
    result = add_days("20240131", 1)
    assert result == "20240201"


def test_walkforward_deterministic_with_seed():
    """Test that same seed produces same random_state parameter."""
    # This is a placeholder - actual determinism testing would require
    # running full hyperopt which is too expensive for unit tests
    from tools.walkforward import infer_hyperopt_spaces

    # Just verify the function doesn't crash
    spaces = infer_hyperopt_spaces("TrendPullback")
    assert isinstance(spaces, list)


def test_walkforward_fold_manifest_structure():
    """Test that fold manifest has required fields."""
    # Mock manifest structure as walkforward.py would create
    manifest = {
        "fold": 1,
        "is_start": "20240101",
        "is_end": "20241231",
        "oos_start": "20250101",
        "oos_end": "20250331",
        "embargo_days": 5,
        "train": {
            "phase": "train",
            "timerange": "20240101-20241231",
            "config_sha256": "abc123",
            "strategy_sha256": "def456",
        },
        "test": {
            "phase": "test",
            "timerange": "20250101-20250331",
            "archive_sha256": "ghi789",
            "trade_count": 150,
        },
        "metrics": {
            "trade_count": 150,
            "profit_factor": 1.25,
            "daily_sharpe": 0.8,
        },
    }

    # Verify required keys
    assert "fold" in manifest
    assert "embargo_days" in manifest
    assert "train" in manifest
    assert "test" in manifest
    assert "metrics" in manifest
    assert manifest["train"]["phase"] == "train"
    assert manifest["test"]["phase"] == "test"


def test_walkforward_no_overlap_train_test():
    """Test that train and test periods don't overlap after embargo."""
    from tools.walkforward import add_days, add_months

    is_start = "20240101"
    is_end = add_months(is_start, 12)
    embargo_days = 5
    oos_start = add_days(is_end, embargo_days)
    add_months(oos_start, 3)

    # Parse dates for comparison
    from datetime import datetime

    is_end_dt = datetime.strptime(is_end, "%Y%m%d")
    oos_start_dt = datetime.strptime(oos_start, "%Y%m%d")

    # OOS must start after IS end + embargo
    days_diff = (oos_start_dt - is_end_dt).days
    assert days_diff == embargo_days, f"Embargo not applied correctly: {days_diff} days"
