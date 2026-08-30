"""
Summary report generator for Freqtrade backtest validation.
Compatible with Freqtrade 2026.7 schema.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone, UTC
from pathlib import Path
from typing import Any


@dataclass
class BacktestMetrics:
    """Normalized backtest metrics with explicit units."""

    # Provenance
    source_file: str
    source_sha256: str
    strategy_name: str
    generated_at: str

    # Period
    backtest_start: str
    backtest_end: str
    backtest_days: int
    timerange: str
    timeframe: str

    # Trade counts
    total_trades: int
    trade_count_long: int
    trade_count_short: int
    trades_per_day: float

    # Returns (both ratio and percent for clarity)
    return_ratio: float  # e.g., 0.1401 for 14.01%
    return_pct: float    # e.g., 14.01
    return_abs_stake: float

    # Long/Short breakdown
    profit_total_long_ratio: float
    profit_total_long_abs: float
    profit_total_short_ratio: float
    profit_total_short_abs: float

    # Risk metrics
    profit_factor: float
    expectancy: float
    expectancy_ratio: float
    sharpe: float
    sortino: float
    calmar: float

    # Drawdown (ratio and percent)
    max_drawdown_account_ratio: float  # e.g., 0.2386 for 23.86%
    max_drawdown_account_pct: float    # e.g., 23.86
    max_drawdown_abs_stake: float

    # Win/loss stats
    wins: int
    draws: int
    losses: int
    winrate: float

    # Other
    rejected_signals: int
    stake_currency: str
    starting_balance: float
    final_balance: float

    # Breakdowns (optional, populated if available)
    results_per_enter_tag: list[dict[str, Any]] | None = None
    results_per_pair: list[dict[str, Any]] | None = None
    exit_reason_summary: list[dict[str, Any]] | None = None
    periodic_breakdown: dict[str, Any] | None = None


def calculate_sha256(path: Path) -> str:
    """Calculate SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def resolve_result_archive(path: Path) -> Path:
    """Resolve a backtest result path to a ZIP archive.

    Args:
        path: Either a ZIP file or a directory containing backtest results

    Returns:
        Path to the ZIP archive to use

    Raises:
        FileNotFoundError: If path doesn't exist or no valid archive found
    """
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")

    if path.is_file() and path.suffix == ".zip":
        return path

    if path.is_dir():
        last_result = path / ".last_result.json"
        if last_result.exists():
            with open(last_result) as f:
                data = json.load(f)
                if "latest_backtest" in data:
                    archive_path = path / data["latest_backtest"]
                    if archive_path.exists():
                        return archive_path

        zips = sorted(path.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        if zips:
            return zips[0]

        raise FileNotFoundError(f"No ZIP archives found in directory: {path}")

    raise ValueError(f"Path must be a ZIP file or directory: {path}")


def load_backtest_summary(path: Path, strategy: str) -> dict[str, Any]:
    """Load backtest summary for a specific strategy from archive.

    Args:
        path: Path to the ZIP archive
        strategy: Strategy name to extract

    Returns:
        Dictionary with strategy results and metadata

    Raises:
        ValueError: If strategy not found in archive or required fields missing
    """
    with zipfile.ZipFile(path, "r") as z:
        files = z.namelist()

        # Find the main result JSON (not config, not strategy source)
        result_file = None
        for name in files:
            if name.endswith(".json") and "config" not in name.lower() and not name.endswith(".py"):
                result_file = name
                break

        if not result_file:
            raise ValueError(f"No result JSON found in {path}")

        with z.open(result_file) as f:
            data = json.load(f)

        if "strategy" not in data:
            raise ValueError(f"Invalid schema: missing 'strategy' key in {path}")

        if strategy not in data["strategy"]:
            available = list(data["strategy"].keys())
            raise ValueError(
                f"Strategy '{strategy}' not found in archive {path}. "
                f"Available: {available}"
            )

        return data["strategy"][strategy]


def parse_to_metrics(
    raw_data: dict[str, Any],
    source_file: str,
    source_sha256: str,
) -> BacktestMetrics:
    """Parse raw Freqtrade 2026.7 schema to normalized metrics.

    Args:
        raw_data: Raw strategy dictionary from Freqtrade export
        source_file: Source archive filename
        source_sha256: SHA256 of source archive

    Returns:
        BacktestMetrics with normalized units

    Raises:
        ValueError: If required fields are missing or have invalid values
    """
    # Validate required fields
    required_fields = [
        "total_trades", "trade_count_long", "trade_count_short",
        "profit_factor", "profit_total", "profit_total_abs",
        "max_drawdown_account", "max_drawdown_abs",
        "backtest_start", "backtest_end", "backtest_days",
        "strategy_name", "stake_currency", "starting_balance", "final_balance",
    ]

    missing = [f for f in required_fields if f not in raw_data]
    if missing:
        raise ValueError(f"Missing required fields in backtest data: {missing}")

    # Extract and validate
    total_trades = raw_data["total_trades"]
    if not isinstance(total_trades, int) or total_trades < 0:
        raise ValueError(f"Invalid total_trades: {total_trades}")

    trade_count_long = raw_data["trade_count_long"]
    trade_count_short = raw_data["trade_count_short"]

    backtest_days = raw_data["backtest_days"]
    if backtest_days <= 0:
        raise ValueError(f"Invalid backtest_days: {backtest_days}")

    trades_per_day = total_trades / backtest_days

    # Returns: profit_total is a ratio in 2026.7
    return_ratio = raw_data["profit_total"]
    return_pct = return_ratio * 100.0
    return_abs_stake = raw_data["profit_total_abs"]

    # Long/short breakdown
    profit_total_long_ratio = raw_data.get("profit_total_long", 0.0)
    profit_total_long_abs = raw_data.get("profit_total_long_abs", 0.0)
    profit_total_short_ratio = raw_data.get("profit_total_short", 0.0)
    profit_total_short_abs = raw_data.get("profit_total_short_abs", 0.0)

    # Drawdown: max_drawdown_account is the ratio, convert to percent
    max_dd_account_ratio = raw_data["max_drawdown_account"]
    max_dd_account_pct = max_dd_account_ratio * 100.0
    max_dd_abs_stake = raw_data["max_drawdown_abs"]

    # Win/loss stats
    wins = raw_data.get("wins", 0)
    draws = raw_data.get("draws", 0)
    losses = raw_data.get("losses", 0)
    winrate = raw_data.get("winrate", 0.0)

    return BacktestMetrics(
        source_file=source_file,
        source_sha256=source_sha256,
        strategy_name=raw_data["strategy_name"],
        generated_at=datetime.now(UTC).isoformat(),
        backtest_start=raw_data["backtest_start"],
        backtest_end=raw_data["backtest_end"],
        backtest_days=backtest_days,
        timerange=raw_data.get("timerange", ""),
        timeframe=raw_data.get("timeframe", ""),
        total_trades=total_trades,
        trade_count_long=trade_count_long,
        trade_count_short=trade_count_short,
        trades_per_day=trades_per_day,
        return_ratio=return_ratio,
        return_pct=return_pct,
        return_abs_stake=return_abs_stake,
        profit_total_long_ratio=profit_total_long_ratio,
        profit_total_long_abs=profit_total_long_abs,
        profit_total_short_ratio=profit_total_short_ratio,
        profit_total_short_abs=profit_total_short_abs,
        profit_factor=raw_data["profit_factor"],
        expectancy=raw_data.get("expectancy", 0.0),
        expectancy_ratio=raw_data.get("expectancy_ratio", 0.0),
        sharpe=raw_data.get("sharpe", 0.0),
        sortino=raw_data.get("sortino", 0.0),
        calmar=raw_data.get("calmar", 0.0),
        max_drawdown_account_ratio=max_dd_account_ratio,
        max_drawdown_account_pct=max_dd_account_pct,
        max_drawdown_abs_stake=max_dd_abs_stake,
        wins=wins,
        draws=draws,
        losses=losses,
        winrate=winrate,
        rejected_signals=raw_data.get("rejected_signals", 0),
        stake_currency=raw_data["stake_currency"],
        starting_balance=raw_data["starting_balance"],
        final_balance=raw_data["final_balance"],
        results_per_enter_tag=raw_data.get("results_per_enter_tag"),
        results_per_pair=raw_data.get("results_per_pair"),
        exit_reason_summary=raw_data.get("exit_reason_summary"),
        periodic_breakdown=raw_data.get("periodic_breakdown"),
    )


def render_summary(metrics: BacktestMetrics) -> str:
    """Render backtest metrics as markdown.

    Args:
        metrics: Normalized backtest metrics

    Returns:
        Markdown-formatted summary report
    """
    lines = ["# Backtest Summary\n"]

    lines.append("## Provenance\n")
    lines.append(f"**Source**: `{metrics.source_file}`")
    lines.append(f"**SHA256**: `{metrics.source_sha256}`")
    lines.append(f"**Strategy**: {metrics.strategy_name}")
    lines.append(f"**Generated**: {metrics.generated_at}")
    lines.append(f"**Timeframe**: {metrics.timeframe}")
    lines.append(f"**Timerange**: {metrics.timerange}\n")

    lines.append("## Period\n")
    lines.append(f"**Start**: {metrics.backtest_start}")
    lines.append(f"**End**: {metrics.backtest_end}")
    lines.append(f"**Days**: {metrics.backtest_days}\n")

    lines.append("## Trade Counts\n")
    lines.append(f"**Total Trades**: {metrics.total_trades}")
    lines.append(f"**Trades/Day**: {metrics.trades_per_day:.2f}")
    lines.append(f"**Long Trades**: {metrics.trade_count_long}")
    lines.append(f"**Short Trades**: {metrics.trade_count_short}\n")

    lines.append("## Returns\n")
    lines.append(f"**Return**: {metrics.return_pct:.4f}% (ratio: {metrics.return_ratio:.6f})")
    lines.append(f"**Return Absolute**: {metrics.return_abs_stake:.2f} {metrics.stake_currency}")
    lines.append(f"**Long Return**: {metrics.profit_total_long_ratio * 100:.2f}% ({metrics.profit_total_long_abs:.2f} {metrics.stake_currency})")
    lines.append(f"**Short Return**: {metrics.profit_total_short_ratio * 100:.2f}% ({metrics.profit_total_short_abs:.2f} {metrics.stake_currency})\n")

    lines.append("## Risk Metrics\n")
    lines.append(f"**Profit Factor**: {metrics.profit_factor:.4f}")
    lines.append(f"**Expectancy**: {metrics.expectancy:.4f} (ratio: {metrics.expectancy_ratio:.4f})")
    lines.append(f"**Max Drawdown (Account)**: {metrics.max_drawdown_account_pct:.4f}% (ratio: {metrics.max_drawdown_account_ratio:.6f})")
    lines.append(f"**Max Drawdown (Abs)**: {metrics.max_drawdown_abs_stake:.2f} {metrics.stake_currency}")
    lines.append(f"**Sharpe**: {metrics.sharpe:.4f}")
    lines.append(f"**Sortino**: {metrics.sortino:.4f}")
    lines.append(f"**Calmar**: {metrics.calmar:.4f}\n")

    lines.append("## Win/Loss Stats\n")
    lines.append(f"**Wins**: {metrics.wins}")
    lines.append(f"**Draws**: {metrics.draws}")
    lines.append(f"**Losses**: {metrics.losses}")
    lines.append(f"**Win Rate**: {metrics.winrate * 100:.2f}%")
    lines.append(f"**Rejected Signals**: {metrics.rejected_signals}\n")

    lines.append("## Balance\n")
    lines.append(f"**Starting**: {metrics.starting_balance:.2f} {metrics.stake_currency}")
    lines.append(f"**Final**: {metrics.final_balance:.2f} {metrics.stake_currency}\n")

    # Breakdowns
    if metrics.results_per_enter_tag:
        lines.append("## Per-Tag Performance\n")
        lines.append("| Tag | Trades | PF | Return % | Win Rate | Sharpe |")
        lines.append("|-----|--------|----|---------|---------:|--------:|")
        for tag_data in metrics.results_per_enter_tag:
            tag = tag_data.get("key", "unknown")
            count = tag_data.get("trades", 0)
            pf = tag_data.get("profit_factor", 0.0)
            profit_pct = tag_data.get("profit_total_pct", 0.0)
            winrate = tag_data.get("winrate", 0.0)
            sharpe = tag_data.get("sharpe", 0.0)
            lines.append(
                f"| {tag} | {count} | {pf:.4f} | {profit_pct:.2f}% | "
                f"{winrate * 100:.2f}% | {sharpe:.4f} |"
            )
        lines.append("")

    if metrics.results_per_pair:
        lines.append("## Per-Pair Performance\n")
        lines.append("| Pair | Trades | PF | Return % | Win Rate | Sharpe |")
        lines.append("|------|--------|----|---------|---------:|--------:|")
        for pair_data in metrics.results_per_pair:
            pair = pair_data.get("key", "unknown")
            count = pair_data.get("trades", 0)
            pf = pair_data.get("profit_factor", 0.0)
            profit_pct = pair_data.get("profit_total_pct", 0.0)
            winrate = pair_data.get("winrate", 0.0)
            sharpe = pair_data.get("sharpe", 0.0)
            lines.append(
                f"| {pair} | {count} | {pf:.4f} | {profit_pct:.2f}% | "
                f"{winrate * 100:.2f}% | {sharpe:.4f} |"
            )
        lines.append("")

    if metrics.exit_reason_summary:
        lines.append("## Exit Reason Summary\n")
        lines.append("| Reason | Trades | PF | Profit % |")
        lines.append("|--------|--------|----|---------:|")
        for reason_data in metrics.exit_reason_summary:
            reason = reason_data.get("key", "unknown")
            count = reason_data.get("trades", 0)
            pf = reason_data.get("profit_factor", 0.0)
            profit_pct = reason_data.get("profit_total_pct", 0.0)
            lines.append(f"| {reason} | {count} | {pf:.4f} | {profit_pct:.2f}% |")
        lines.append("")

    # Temporal breakdown
    if metrics.periodic_breakdown:
        breakdown = metrics.periodic_breakdown

        if "year" in breakdown:
            lines.append("## Yearly Performance\n")
            lines.append("| Year | Trades | PF | Return % | Win Rate |")
            lines.append("|------|--------|----|---------:|---------:|")
            for year_data in breakdown["year"]:
                year = year_data.get("date", "unknown")
                count = year_data.get("trades", 0)
                pf = year_data.get("profit_factor", 0.0)
                profit_pct = year_data.get("profit_total_pct", 0.0)
                winrate = year_data.get("winrate", 0.0)
                flag = " ⚠" if pf < 1.0 else ""
                lines.append(f"| {year} | {count} | {pf:.4f}{flag} | {profit_pct:.2f}% | {winrate * 100:.2f}% |")
            lines.append("")

        if "quarter" in breakdown:
            lines.append("## Quarterly Performance\n")
            lines.append("| Quarter | Trades | PF | Return % | Win Rate |")
            lines.append("|---------|--------|----|---------:|---------:|")
            for q_data in breakdown["quarter"]:
                quarter = q_data.get("date", "unknown")
                count = q_data.get("trades", 0)
                pf = q_data.get("profit_factor", 0.0)
                profit_pct = q_data.get("profit_total_pct", 0.0)
                winrate = q_data.get("winrate", 0.0)
                flag = " ⚠" if pf < 1.0 else ""
                lines.append(f"| {quarter} | {count} | {pf:.4f}{flag} | {profit_pct:.2f}% | {winrate * 100:.2f}% |")
            lines.append("\n**Note:** ⚠ indicates PF < 1.0 (losing period)")

    return "\n".join(lines)


def render_comparison(baseline: BacktestMetrics, candidate: BacktestMetrics) -> str:
    """Render a comparison between baseline and candidate results.

    Args:
        baseline: Baseline backtest metrics
        candidate: Candidate backtest metrics

    Returns:
        Markdown-formatted comparison report
    """
    lines = ["# Backtest Comparison\n"]

    lines.append("## Provenance\n")
    lines.append(f"**Baseline**: `{baseline.source_file}` (SHA256: `{baseline.source_sha256[:16]}...`)")
    lines.append(f"**Candidate**: `{candidate.source_file}` (SHA256: `{candidate.source_sha256[:16]}...`)")
    lines.append(f"**Generated**: {candidate.generated_at}\n")

    lines.append("## Overview\n")
    lines.append("| Metric | Baseline | Candidate | Delta | Delta % |")
    lines.append("|--------|----------|-----------|------:|--------:|")

    def format_comparison(label: str, b_val: float, c_val: float, precision: int = 4) -> str:
        delta = c_val - b_val
        delta_pct = (delta / b_val * 100) if b_val != 0 else 0
        fmt = f"{{:.{precision}f}}"
        return (
            f"| {label} | {fmt.format(b_val)} | {fmt.format(c_val)} | "
            f"{delta:+.{precision}f} | {delta_pct:+.2f}% |"
        )

    lines.append(format_comparison("Total Trades", baseline.total_trades, candidate.total_trades, 0))
    lines.append(format_comparison("Trades/Day", baseline.trades_per_day, candidate.trades_per_day, 2))
    lines.append(format_comparison("Long Trades", baseline.trade_count_long, candidate.trade_count_long, 0))
    lines.append(format_comparison("Short Trades", baseline.trade_count_short, candidate.trade_count_short, 0))
    lines.append(format_comparison("Profit Factor", baseline.profit_factor, candidate.profit_factor, 4))
    lines.append(format_comparison("Return %", baseline.return_pct, candidate.return_pct, 2))
    lines.append(format_comparison("Expectancy", baseline.expectancy, candidate.expectancy, 4))
    lines.append(format_comparison("Max DD %", baseline.max_drawdown_account_pct, candidate.max_drawdown_account_pct, 2))
    lines.append(format_comparison("Sharpe", baseline.sharpe, candidate.sharpe, 4))
    lines.append(format_comparison("Win Rate %", baseline.winrate * 100, candidate.winrate * 100, 2))

    lines.append("\n## Candidate Tag Performance\n")
    if candidate.results_per_enter_tag:
        lines.append("| Tag | Trades | PF | Return % |")
        lines.append("|-----|--------|----|---------:|")
        for tag_data in candidate.results_per_enter_tag:
            tag = tag_data.get("key", "unknown")
            count = tag_data.get("trades", 0)
            pf = tag_data.get("profit_factor", 0.0)
            profit_pct = tag_data.get("profit_total_pct", 0.0)
            lines.append(f"| {tag} | {count} | {pf:.4f} | {profit_pct:.2f}% |")
    else:
        lines.append("No tag performance data available.")

    return "\n".join(lines)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate backtest validation report (Freqtrade 2026.7 schema)"
    )
    parser.add_argument("--results", help="Path to backtest ZIP or directory")
    parser.add_argument("--baseline", help="Baseline backtest ZIP for comparison")
    parser.add_argument("--candidate", help="Candidate backtest ZIP or directory for comparison")
    parser.add_argument("--strategy", required=True, help="Strategy name")
    parser.add_argument("--output", required=True, help="Output markdown file path")
    return parser.parse_args()


def main() -> int:
    """Main entry point. Returns exit code."""
    try:
        args = parse_args()

        if args.baseline and args.candidate:
            # Comparison mode
            baseline_archive = resolve_result_archive(Path(args.baseline))
            candidate_archive = resolve_result_archive(Path(args.candidate))

            baseline_sha256 = calculate_sha256(baseline_archive)
            candidate_sha256 = calculate_sha256(candidate_archive)

            baseline_raw = load_backtest_summary(baseline_archive, args.strategy)
            candidate_raw = load_backtest_summary(candidate_archive, args.strategy)

            baseline_metrics = parse_to_metrics(
                baseline_raw, baseline_archive.name, baseline_sha256
            )
            candidate_metrics = parse_to_metrics(
                candidate_raw, candidate_archive.name, candidate_sha256
            )

            report = render_comparison(baseline_metrics, candidate_metrics)

        elif args.results:
            # Single report mode
            archive = resolve_result_archive(Path(args.results))
            archive_sha256 = calculate_sha256(archive)
            raw_data = load_backtest_summary(archive, args.strategy)
            metrics = parse_to_metrics(raw_data, archive.name, archive_sha256)
            report = render_summary(metrics)

        else:
            print("Error: Must provide either --results or both --baseline and --candidate", file=sys.stderr)
            return 1

        # Write output
        output_path = Path(args.output)

        # Check if output already exists to prevent overwriting
        if output_path.exists():
            # Create timestamped version instead
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            stem = output_path.stem
            suffix = output_path.suffix
            output_path = output_path.parent / f"{stem}_{timestamp}{suffix}"
            print(f"Warning: Output exists, using {output_path}", file=sys.stderr)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"Report written to {output_path}")
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
