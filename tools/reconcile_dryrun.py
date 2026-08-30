#!/usr/bin/env python3
"""
Dry-run reconciliation tool - compares expected signals vs actual DB trades.

Read-only tool that analyzes:
- Expected entry signals from closed candles
- Actual orders/trades in database
- Blocked-by-guard signals (denied entries)
- Rejected, missed, duplicate, delayed signals

Usage:
    python tools/reconcile_dryrun.py --db path/to/tradesv3.dryrun.sqlite --strategy TrendPullback --timerange 20260820-20260829
"""

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd


@dataclass
class ExpectedSignal:
    """Signal that strategy should have generated."""
    timestamp: datetime
    pair: str
    side: str  # "long" or "short"
    price: float
    reason: str  # entry tag


@dataclass
class ActualTrade:
    """Trade from database."""
    id: int
    open_date: datetime
    pair: str
    is_short: bool
    open_rate: float
    stake_amount: float
    enter_tag: Optional[str]
    exit_reason: Optional[str]


@dataclass
class ReconciliationResult:
    """Result of signal vs trade comparison."""
    signal_timestamp: datetime
    pair: str
    side: str
    status: str  # "matched", "blocked", "rejected", "missed", "duplicate", "delayed"
    signal_price: float
    actual_trade_id: Optional[int]
    actual_price: Optional[float]
    delay_seconds: Optional[float]
    reason: str


class DryRunReconciler:
    """Reconciles expected signals with actual dry-run trades."""

    def __init__(self, db_path: Path, match_tolerance_seconds: float = 300):
        """
        Args:
            db_path: Path to tradesv3.sqlite database
            match_tolerance_seconds: Max time difference to consider signal/trade matched
        """
        self.db_path = db_path
        self.match_tolerance_seconds = match_tolerance_seconds
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        """Connect to database (read-only)."""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

        # Open in read-only mode
        self.conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def load_trades(self, strategy: str, timerange: tuple[datetime, datetime]) -> List[ActualTrade]:
        """
        Load trades from database.

        Args:
            strategy: Strategy name filter
            timerange: (start, end) datetime tuple

        Returns:
            List of ActualTrade objects
        """
        if not self.conn:
            raise RuntimeError("Not connected to database")

        start_ts = int(timerange[0].timestamp() * 1000)
        end_ts = int(timerange[1].timestamp() * 1000)

        query = """
            SELECT
                id,
                open_date,
                pair,
                is_short,
                open_rate,
                stake_amount,
                enter_tag,
                exit_reason
            FROM trades
            WHERE strategy = ?
              AND open_date >= ?
              AND open_date <= ?
            ORDER BY open_date
        """

        cursor = self.conn.execute(query, (strategy, start_ts, end_ts))
        trades = []

        for row in cursor:
            trades.append(ActualTrade(
                id=row["id"],
                open_date=datetime.fromtimestamp(row["open_date"] / 1000, tz=timezone.utc),
                pair=row["pair"],
                is_short=bool(row["is_short"]),
                open_rate=row["open_rate"],
                stake_amount=row["stake_amount"],
                enter_tag=row["enter_tag"],
                exit_reason=row["exit_reason"]
            ))

        return trades

    def match_signals_to_trades(
        self,
        signals: List[ExpectedSignal],
        trades: List[ActualTrade]
    ) -> List[ReconciliationResult]:
        """
        Match expected signals to actual trades.

        Matching criteria:
        - Same pair
        - Same side (long/short)
        - Within time tolerance
        - Not already matched

        Args:
            signals: Expected entry signals
            trades: Actual trades from DB

        Returns:
            List of reconciliation results
        """
        results = []
        matched_trade_ids = set()

        for signal in signals:
            matched = False

            for trade in trades:
                if trade.id in matched_trade_ids:
                    continue

                # Check pair match
                if signal.pair != trade.pair:
                    continue

                # Check side match
                signal_is_short = (signal.side == "short")
                if signal_is_short != trade.is_short:
                    continue

                # Check time tolerance
                delay = (trade.open_date - signal.timestamp).total_seconds()
                if abs(delay) > self.match_tolerance_seconds:
                    continue

                # Match found
                matched = True
                matched_trade_ids.add(trade.id)

                status = "matched"
                if delay > 60:
                    status = "delayed"

                results.append(ReconciliationResult(
                    signal_timestamp=signal.timestamp,
                    pair=signal.pair,
                    side=signal.side,
                    status=status,
                    signal_price=signal.price,
                    actual_trade_id=trade.id,
                    actual_price=trade.open_rate,
                    delay_seconds=delay,
                    reason=f"Matched with trade {trade.id}, delay {delay:.1f}s"
                ))
                break

            if not matched:
                # Signal not matched - could be blocked, rejected, or missed
                results.append(ReconciliationResult(
                    signal_timestamp=signal.timestamp,
                    pair=signal.pair,
                    side=signal.side,
                    status="missed",
                    signal_price=signal.price,
                    actual_trade_id=None,
                    actual_price=None,
                    delay_seconds=None,
                    reason="Signal not executed (possible guard block or rejection)"
                ))

        # Check for trades without matching signals (unexpected trades)
        for trade in trades:
            if trade.id not in matched_trade_ids:
                results.append(ReconciliationResult(
                    signal_timestamp=trade.open_date,
                    pair=trade.pair,
                    side="short" if trade.is_short else "long",
                    status="unexpected",
                    signal_price=trade.open_rate,
                    actual_trade_id=trade.id,
                    actual_price=trade.open_rate,
                    delay_seconds=0.0,
                    reason=f"Trade {trade.id} executed without matching signal"
                ))

        return sorted(results, key=lambda r: r.signal_timestamp)

    def generate_report(
        self,
        results: List[ReconciliationResult],
        output_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Generate reconciliation report.

        Args:
            results: Reconciliation results
            output_path: Optional path to save JSON report

        Returns:
            Report dictionary
        """
        # Count by status
        status_counts = {}
        for result in results:
            status_counts[result.status] = status_counts.get(result.status, 0) + 1

        # Calculate metrics
        total_signals = len([r for r in results if r.status != "unexpected"])
        matched = len([r for r in results if r.status in ("matched", "delayed")])
        missed = len([r for r in results if r.status == "missed"])
        unexpected = len([r for r in results if r.status == "unexpected"])

        match_rate = (matched / total_signals * 100) if total_signals > 0 else 0.0
        miss_rate = (missed / total_signals * 100) if total_signals > 0 else 0.0

        # Average delay for matched trades
        delays = [r.delay_seconds for r in results if r.delay_seconds is not None]
        avg_delay = sum(delays) / len(delays) if delays else 0.0

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_signals": total_signals,
                "matched": matched,
                "missed": missed,
                "unexpected": unexpected,
                "match_rate_pct": round(match_rate, 2),
                "miss_rate_pct": round(miss_rate, 2),
                "avg_delay_seconds": round(avg_delay, 2)
            },
            "status_counts": status_counts,
            "results": [asdict(r) for r in results]
        }

        if output_path:
            with open(output_path, "w") as f:
                json.dump(report, f, indent=2, default=str)

        return report


def parse_timerange(timerange_str: str) -> tuple[datetime, datetime]:
    """Parse timerange string like '20260820-20260829'."""
    start_str, end_str = timerange_str.split("-")
    start = datetime.strptime(start_str, "%Y%m%d").replace(tzinfo=timezone.utc)
    end = datetime.strptime(end_str, "%Y%m%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
    return start, end


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Reconcile expected signals vs actual dry-run trades",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--db",
        type=Path,
        required=True,
        help="Path to tradesv3.dryrun.sqlite database"
    )
    parser.add_argument(
        "--strategy",
        type=str,
        required=True,
        help="Strategy name to filter"
    )
    parser.add_argument(
        "--timerange",
        type=str,
        required=True,
        help="Timerange in format YYYYMMDD-YYYYMMDD"
    )
    parser.add_argument(
        "--signals",
        type=Path,
        help="JSON file with expected signals (for testing)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON report path"
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=300,
        help="Match tolerance in seconds (default: 300)"
    )

    args = parser.parse_args()

    try:
        # Parse timerange
        timerange = parse_timerange(args.timerange)

        # Create reconciler
        reconciler = DryRunReconciler(args.db, match_tolerance_seconds=args.tolerance)
        reconciler.connect()

        # Load trades
        trades = reconciler.load_trades(args.strategy, timerange)
        print(f"Loaded {len(trades)} trades from database")

        # Load signals (from file or generate placeholder)
        if args.signals:
            with open(args.signals) as f:
                signal_data = json.load(f)
                signals = [
                    ExpectedSignal(
                        timestamp=datetime.fromisoformat(s["timestamp"]),
                        pair=s["pair"],
                        side=s["side"],
                        price=s["price"],
                        reason=s["reason"]
                    )
                    for s in signal_data
                ]
        else:
            # No signals provided - can only detect unexpected trades
            print("WARNING: No signals file provided, only unexpected trades will be detected")
            signals = []

        print(f"Loaded {len(signals)} expected signals")

        # Reconcile
        results = reconciler.match_signals_to_trades(signals, trades)

        # Generate report
        report = reconciler.generate_report(results, args.output)

        # Print summary
        print("\n" + "=" * 60)
        print("RECONCILIATION SUMMARY")
        print("=" * 60)
        print(f"Total signals:   {report['summary']['total_signals']}")
        print(f"Matched trades:  {report['summary']['matched']}")
        print(f"Missed signals:  {report['summary']['missed']}")
        print(f"Unexpected:      {report['summary']['unexpected']}")
        print(f"Match rate:      {report['summary']['match_rate_pct']}%")
        print(f"Miss rate:       {report['summary']['miss_rate_pct']}%")
        print(f"Avg delay:       {report['summary']['avg_delay_seconds']}s")
        print("=" * 60)

        if args.output:
            print(f"\nFull report saved to: {args.output}")

        reconciler.close()

        # Exit code based on miss rate
        miss_rate = report['summary']['miss_rate_pct']
        if miss_rate > 10.0:
            print(f"\nWARNING: High miss rate ({miss_rate}%) - investigate guard blocks")
            return 1

        return 0

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
