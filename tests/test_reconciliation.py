"""Tests for dry-run reconciliation tool."""

import json
import sqlite3
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from tools.reconcile_dryrun import (
    DryRunReconciler,
    ExpectedSignal,
    ActualTrade,
    ReconciliationResult,
    parse_timerange
)


@pytest.fixture
def temp_db():
    """Create temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as f:
        db_path = Path(f.name)

    # Create schema
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE trades (
            id INTEGER PRIMARY KEY,
            open_date INTEGER NOT NULL,
            pair TEXT NOT NULL,
            is_short INTEGER NOT NULL,
            open_rate REAL NOT NULL,
            stake_amount REAL NOT NULL,
            enter_tag TEXT,
            exit_reason TEXT,
            strategy TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    db_path.unlink()


def test_parse_timerange():
    """Test timerange parsing."""
    start, end = parse_timerange("20260820-20260829")

    assert start == datetime(2026, 8, 20, 0, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 8, 29, 23, 59, 59, tzinfo=timezone.utc)


def test_reconciler_connect_missing_db():
    """Test connecting to non-existent database."""
    reconciler = DryRunReconciler(Path("/nonexistent/db.sqlite"))

    with pytest.raises(FileNotFoundError):
        reconciler.connect()


def test_load_trades_empty(temp_db):
    """Test loading trades from empty database."""
    reconciler = DryRunReconciler(temp_db)
    reconciler.connect()

    timerange = (
        datetime(2026, 8, 20, tzinfo=timezone.utc),
        datetime(2026, 8, 29, tzinfo=timezone.utc)
    )

    trades = reconciler.load_trades("TestStrategy", timerange)
    assert len(trades) == 0

    reconciler.close()


def test_load_trades_with_data(temp_db):
    """Test loading trades with data."""
    # Insert test data
    conn = sqlite3.connect(temp_db)
    base_time = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

    conn.execute("""
        INSERT INTO trades (id, open_date, pair, is_short, open_rate, stake_amount, enter_tag, exit_reason, strategy)
        VALUES (1, ?, 'BTC/USDT', 0, 50000.0, 100.0, 'long_entry', NULL, 'TestStrategy')
    """, (int(base_time.timestamp() * 1000),))

    conn.execute("""
        INSERT INTO trades (id, open_date, pair, is_short, open_rate, stake_amount, enter_tag, exit_reason, strategy)
        VALUES (2, ?, 'ETH/USDT', 1, 3000.0, 100.0, 'short_entry', NULL, 'TestStrategy')
    """, (int((base_time + timedelta(hours=1)).timestamp() * 1000),))

    conn.commit()
    conn.close()

    # Load trades
    reconciler = DryRunReconciler(temp_db)
    reconciler.connect()

    timerange = (
        datetime(2026, 8, 20, tzinfo=timezone.utc),
        datetime(2026, 8, 29, tzinfo=timezone.utc)
    )

    trades = reconciler.load_trades("TestStrategy", timerange)

    assert len(trades) == 2
    assert trades[0].pair == "BTC/USDT"
    assert trades[0].is_short is False
    assert trades[1].pair == "ETH/USDT"
    assert trades[1].is_short is True

    reconciler.close()


def test_match_signals_perfect_match(temp_db):
    """Test matching signals with perfect timing."""
    base_time = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

    signals = [
        ExpectedSignal(
            timestamp=base_time,
            pair="BTC/USDT",
            side="long",
            price=50000.0,
            reason="test_entry"
        )
    ]

    trades = [
        ActualTrade(
            id=1,
            open_date=base_time + timedelta(seconds=10),
            pair="BTC/USDT",
            is_short=False,
            open_rate=50005.0,
            stake_amount=100.0,
            enter_tag="test_entry",
            exit_reason=None
        )
    ]

    reconciler = DryRunReconciler(temp_db)
    results = reconciler.match_signals_to_trades(signals, trades)

    assert len(results) == 1
    assert results[0].status == "matched"
    assert results[0].actual_trade_id == 1
    assert results[0].delay_seconds == 10.0


def test_match_signals_delayed_match(temp_db):
    """Test matching signals with delay."""
    base_time = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

    signals = [
        ExpectedSignal(
            timestamp=base_time,
            pair="BTC/USDT",
            side="long",
            price=50000.0,
            reason="test_entry"
        )
    ]

    trades = [
        ActualTrade(
            id=1,
            open_date=base_time + timedelta(seconds=120),  # 2 minute delay
            pair="BTC/USDT",
            is_short=False,
            open_rate=50005.0,
            stake_amount=100.0,
            enter_tag="test_entry",
            exit_reason=None
        )
    ]

    reconciler = DryRunReconciler(temp_db)
    results = reconciler.match_signals_to_trades(signals, trades)

    assert len(results) == 1
    assert results[0].status == "delayed"
    assert results[0].delay_seconds == 120.0


def test_match_signals_missed(temp_db):
    """Test signal without matching trade (missed)."""
    base_time = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

    signals = [
        ExpectedSignal(
            timestamp=base_time,
            pair="BTC/USDT",
            side="long",
            price=50000.0,
            reason="test_entry"
        )
    ]

    trades = []  # No trades

    reconciler = DryRunReconciler(temp_db)
    results = reconciler.match_signals_to_trades(signals, trades)

    assert len(results) == 1
    assert results[0].status == "missed"
    assert results[0].actual_trade_id is None


def test_match_signals_unexpected_trade(temp_db):
    """Test trade without matching signal (unexpected)."""
    base_time = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

    signals = []  # No signals

    trades = [
        ActualTrade(
            id=1,
            open_date=base_time,
            pair="BTC/USDT",
            is_short=False,
            open_rate=50000.0,
            stake_amount=100.0,
            enter_tag="test_entry",
            exit_reason=None
        )
    ]

    reconciler = DryRunReconciler(temp_db)
    results = reconciler.match_signals_to_trades(signals, trades)

    assert len(results) == 1
    assert results[0].status == "unexpected"
    assert results[0].actual_trade_id == 1


def test_match_signals_wrong_pair(temp_db):
    """Test signal and trade with different pairs (no match)."""
    base_time = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

    signals = [
        ExpectedSignal(
            timestamp=base_time,
            pair="BTC/USDT",
            side="long",
            price=50000.0,
            reason="test_entry"
        )
    ]

    trades = [
        ActualTrade(
            id=1,
            open_date=base_time,
            pair="ETH/USDT",  # Wrong pair
            is_short=False,
            open_rate=3000.0,
            stake_amount=100.0,
            enter_tag="test_entry",
            exit_reason=None
        )
    ]

    reconciler = DryRunReconciler(temp_db)
    results = reconciler.match_signals_to_trades(signals, trades)

    assert len(results) == 2
    # Signal missed
    assert any(r.status == "missed" and r.pair == "BTC/USDT" for r in results)
    # Trade unexpected
    assert any(r.status == "unexpected" and r.pair == "ETH/USDT" for r in results)


def test_match_signals_wrong_side(temp_db):
    """Test signal and trade with different sides (no match)."""
    base_time = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

    signals = [
        ExpectedSignal(
            timestamp=base_time,
            pair="BTC/USDT",
            side="long",
            price=50000.0,
            reason="test_entry"
        )
    ]

    trades = [
        ActualTrade(
            id=1,
            open_date=base_time,
            pair="BTC/USDT",
            is_short=True,  # Signal is long, trade is short
            open_rate=50000.0,
            stake_amount=100.0,
            enter_tag="test_entry",
            exit_reason=None
        )
    ]

    reconciler = DryRunReconciler(temp_db)
    results = reconciler.match_signals_to_trades(signals, trades)

    assert len(results) == 2
    assert any(r.status == "missed" and r.side == "long" for r in results)
    assert any(r.status == "unexpected" and r.side == "short" for r in results)


def test_match_signals_outside_tolerance(temp_db):
    """Test signal and trade outside time tolerance (no match)."""
    base_time = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

    signals = [
        ExpectedSignal(
            timestamp=base_time,
            pair="BTC/USDT",
            side="long",
            price=50000.0,
            reason="test_entry"
        )
    ]

    trades = [
        ActualTrade(
            id=1,
            open_date=base_time + timedelta(seconds=400),  # Beyond 300s tolerance
            pair="BTC/USDT",
            is_short=False,
            open_rate=50000.0,
            stake_amount=100.0,
            enter_tag="test_entry",
            exit_reason=None
        )
    ]

    reconciler = DryRunReconciler(temp_db, match_tolerance_seconds=300)
    results = reconciler.match_signals_to_trades(signals, trades)

    assert len(results) == 2
    assert any(r.status == "missed" for r in results)
    assert any(r.status == "unexpected" for r in results)


def test_generate_report():
    """Test report generation."""
    base_time = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

    results = [
        ReconciliationResult(
            signal_timestamp=base_time,
            pair="BTC/USDT",
            side="long",
            status="matched",
            signal_price=50000.0,
            actual_trade_id=1,
            actual_price=50005.0,
            delay_seconds=10.0,
            reason="Matched"
        ),
        ReconciliationResult(
            signal_timestamp=base_time + timedelta(hours=1),
            pair="ETH/USDT",
            side="short",
            status="missed",
            signal_price=3000.0,
            actual_trade_id=None,
            actual_price=None,
            delay_seconds=None,
            reason="Blocked"
        )
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "report.json"
        reconciler = DryRunReconciler(Path("/tmp/dummy.db"))
        report = reconciler.generate_report(results, output_path)

        # Check summary
        assert report["summary"]["total_signals"] == 2
        assert report["summary"]["matched"] == 1
        assert report["summary"]["missed"] == 1
        assert report["summary"]["match_rate_pct"] == 50.0
        assert report["summary"]["miss_rate_pct"] == 50.0
        assert report["summary"]["avg_delay_seconds"] == 10.0

        # Check file was created
        assert output_path.exists()

        # Load and verify JSON
        with open(output_path) as f:
            loaded = json.load(f)
            assert loaded["summary"]["total_signals"] == 2
