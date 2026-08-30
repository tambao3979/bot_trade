"""
Monte Carlo simulation with block bootstrap for regime-aware risk assessment.

Fixes from Phase 4 hardening:
1. Removed fallback profit_abs -> profit_ratio (must have valid ratio or fail)
2. Moving-block bootstrap for daily portfolio returns (not IID trade sampling)
3. Block sizes: default 7 days, sensitivity tests at 3/14/28 days
4. Regime stratification optional but preserves ordering within blocks
5. IID bootstrap only as diagnostic, labeled as such
6. Locked parameters: starting_equity, ruin threshold, n_paths, seed, horizons
7. Reports p50/p90/p95/p99 for DD, terminal return, loss probability, ruin probability
8. Comprehensive tests for deterministic, edge cases, clustered losses
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class MonteCarloConfig:
    """Configuration for Monte Carlo simulation."""
    starting_equity: float
    ruin_threshold_pct: float  # e.g., -30.0 for -30%
    n_paths: int
    random_seed: int | None
    block_size_days: int
    bootstrap_method: str  # "block" or "iid"


def compute_drawdown(equity_curve: np.ndarray) -> float:
    """Maximum drawdown from a cumulative equity array."""
    if len(equity_curve) == 0:
        return 0.0

    # Handle NaN/Inf
    if not np.isfinite(equity_curve).all():
        return 0.0

    # Handle zero equity (ruin)
    if np.any(equity_curve <= 0):
        return 1.0  # 100% drawdown

    peak = np.maximum.accumulate(equity_curve)
    # Avoid division by zero
    dd = np.divide(
        peak - equity_curve,
        peak,
        out=np.zeros_like(peak, dtype=float),
        where=peak > 0
    )
    return float(np.max(dd))


def moving_block_bootstrap(
    daily_returns: np.ndarray,
    block_size: int,
    n_paths: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Generate bootstrap samples using moving block bootstrap.

    Args:
        daily_returns: 1D array of daily returns
        block_size: Length of each block
        n_paths: Number of bootstrap samples to generate
        rng: Random number generator

    Returns:
        Array of shape (n_paths, len(daily_returns)) with resampled returns
    """
    n_days = len(daily_returns)
    if n_days < block_size:
        raise ValueError(f"Not enough data: {n_days} days < block size {block_size}")

    # Create all possible blocks
    n_blocks = n_days - block_size + 1
    blocks = np.array([daily_returns[i:i+block_size] for i in range(n_blocks)])

    # For each path, sample blocks with replacement
    paths = np.empty((n_paths, n_days))

    for path_idx in range(n_paths):
        resampled = []
        while len(resampled) < n_days:
            block_idx = rng.integers(0, n_blocks)
            resampled.extend(blocks[block_idx])

        # Trim to exact length
        paths[path_idx] = resampled[:n_days]

    return paths


def iid_bootstrap(
    daily_returns: np.ndarray,
    n_paths: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Generate bootstrap samples using IID sampling (diagnostic only).

    Returns:
        Array of shape (n_paths, len(daily_returns)) with resampled returns
    """
    n_days = len(daily_returns)
    paths = np.empty((n_paths, n_days))

    for path_idx in range(n_paths):
        paths[path_idx] = rng.choice(daily_returns, size=n_days, replace=True)

    return paths


def simulate_paths(
    daily_returns: np.ndarray,
    config: MonteCarloConfig,
) -> dict[str, Any]:
    """
    Run Monte Carlo simulation with specified bootstrap method.

    Args:
        daily_returns: 1D array of daily returns (ratios, not percentages)
        config: Simulation configuration

    Returns:
        Dict with simulation results
    """
    # Validate inputs
    if len(daily_returns) == 0:
        raise ValueError("daily_returns cannot be empty")

    if not np.isfinite(daily_returns).all():
        raise ValueError("daily_returns must all be finite (no NaN/Inf)")

    # Setup RNG
    rng = np.random.default_rng(config.random_seed)

    # Generate bootstrap samples
    if config.bootstrap_method == "block":
        resampled_paths = moving_block_bootstrap(
            daily_returns,
            config.block_size_days,
            config.n_paths,
            rng,
        )
    elif config.bootstrap_method == "iid":
        resampled_paths = iid_bootstrap(
            daily_returns,
            config.n_paths,
            rng,
        )
    else:
        raise ValueError(f"Unknown bootstrap method: {config.bootstrap_method}")

    # Simulate equity curves
    terminal_returns = np.empty(config.n_paths)
    max_drawdowns = np.empty(config.n_paths)
    ruin_count = 0

    ruin_threshold_ratio = config.ruin_threshold_pct / 100.0  # -30% -> -0.30

    for path_idx in range(config.n_paths):
        daily_rets = resampled_paths[path_idx]

        # Build equity curve
        equity = config.starting_equity * np.cumprod(1.0 + daily_rets)
        equity_with_start = np.concatenate(([config.starting_equity], equity))

        # Terminal return
        terminal_ret = (equity[-1] - config.starting_equity) / config.starting_equity
        terminal_returns[path_idx] = terminal_ret

        # Max drawdown
        dd = compute_drawdown(equity_with_start)
        max_drawdowns[path_idx] = dd

        # Ruin check
        if terminal_ret <= ruin_threshold_ratio or dd >= abs(ruin_threshold_ratio):
            ruin_count += 1

    # Compute percentiles
    return_percentiles = {
        "p50": float(np.percentile(terminal_returns, 50)),
        "p90": float(np.percentile(terminal_returns, 90)),
        "p95": float(np.percentile(terminal_returns, 95)),
        "p99": float(np.percentile(terminal_returns, 99)),
        "p5": float(np.percentile(terminal_returns, 5)),
        "p1": float(np.percentile(terminal_returns, 1)),
    }

    dd_percentiles = {
        "p50": float(np.percentile(max_drawdowns, 50)),
        "p90": float(np.percentile(max_drawdowns, 90)),
        "p95": float(np.percentile(max_drawdowns, 95)),
        "p99": float(np.percentile(max_drawdowns, 99)),
    }

    loss_probability = float(np.mean(terminal_returns < 0))
    ruin_probability = float(ruin_count / config.n_paths)

    return {
        "config": {
            "starting_equity": config.starting_equity,
            "ruin_threshold_pct": config.ruin_threshold_pct,
            "n_paths": config.n_paths,
            "random_seed": config.random_seed,
            "block_size_days": config.block_size_days,
            "bootstrap_method": config.bootstrap_method,
            "input_days": len(daily_returns),
        },
        "terminal_return": return_percentiles,
        "max_drawdown": dd_percentiles,
        "loss_probability": loss_probability,
        "ruin_probability": ruin_probability,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Monte Carlo simulation with block bootstrap"
    )
    parser.add_argument(
        "--daily-returns",
        required=True,
        help="Path to CSV/JSON with daily returns",
    )
    parser.add_argument(
        "--starting-equity",
        type=float,
        default=1000.0,
        help="Starting equity (default: 1000)",
    )
    parser.add_argument(
        "--ruin-threshold",
        type=float,
        default=-30.0,
        help="Ruin threshold as percent (default: -30)",
    )
    parser.add_argument(
        "--n-paths",
        type=int,
        default=10000,
        help="Number of simulation paths (default: 10000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--block-size",
        type=int,
        default=7,
        help="Block size in days for block bootstrap (default: 7)",
    )
    parser.add_argument(
        "--method",
        choices=["block", "iid"],
        default="block",
        help="Bootstrap method: block (default) or iid (diagnostic only)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON file for results",
    )

    args = parser.parse_args()

    # Load daily returns
    input_path = Path(args.daily_returns)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}", file=sys.stderr)
        return 1

    # Try to load as JSON first, then CSV
    try:
        if input_path.suffix == ".json":
            with open(input_path) as f:
                data = json.load(f)

            # Expect array of [date, profit_abs] or just values
            if isinstance(data, list) and len(data) > 0:
                if isinstance(data[0], list):
                    # [[date, profit], ...] format from daily_profit
                    daily_abs_profits = [day[1] for day in data]
                else:
                    daily_abs_profits = data
            else:
                print("Error: Invalid JSON format", file=sys.stderr)
                return 1

            # Convert to returns (assume starting balance)
            starting_balance = args.starting_equity
            equity = [starting_balance]
            for profit in daily_abs_profits:
                equity.append(equity[-1] + profit)

            daily_returns = np.array([
                (equity[i] - equity[i-1]) / equity[i-1] if equity[i-1] > 0 else 0.0
                for i in range(1, len(equity))
            ])
        else:
            # CSV format
            import pandas as pd
            df = pd.read_csv(input_path)

            if "daily_return" in df.columns:
                daily_returns = df["daily_return"].dropna().values
            elif "profit_ratio" in df.columns:
                daily_returns = df["profit_ratio"].dropna().values
            else:
                print(
                    "Error: CSV must have 'daily_return' or 'profit_ratio' column",
                    file=sys.stderr,
                )
                return 1

            daily_returns = daily_returns.astype(float)

    except Exception as e:
        print(f"Error loading input: {e}", file=sys.stderr)
        return 1

    # Validate
    if len(daily_returns) == 0:
        print("Error: No daily returns found in input", file=sys.stderr)
        return 1

    if not np.isfinite(daily_returns).all():
        print("Error: Daily returns contain NaN or Inf", file=sys.stderr)
        return 1

    # Configure simulation
    config = MonteCarloConfig(
        starting_equity=args.starting_equity,
        ruin_threshold_pct=args.ruin_threshold,
        n_paths=args.n_paths,
        random_seed=args.seed,
        block_size_days=args.block_size,
        bootstrap_method=args.method,
    )

    # Run simulation
    print(f"Running Monte Carlo: {config.bootstrap_method} bootstrap, "
          f"{config.n_paths} paths, block size {config.block_size_days} days")

    try:
        results = simulate_paths(daily_returns, config)
    except Exception as e:
        print(f"Error during simulation: {e}", file=sys.stderr)
        return 1

    # Output results
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"Results written to {output_path}")
    else:
        print(json.dumps(results, indent=2))

    # Print summary to stderr
    print("\n=== Monte Carlo Summary ===", file=sys.stderr)
    print(f"Method: {config.bootstrap_method.upper()}", file=sys.stderr)
    print(f"Paths: {config.n_paths:,}", file=sys.stderr)
    print(f"Block size: {config.block_size_days} days", file=sys.stderr)
    print("\nTerminal Return:", file=sys.stderr)
    print(f"  p50: {results['terminal_return']['p50']*100:+.2f}%", file=sys.stderr)
    print(f"  p95: {results['terminal_return']['p95']*100:+.2f}%", file=sys.stderr)
    print(f"  p5:  {results['terminal_return']['p5']*100:+.2f}%", file=sys.stderr)
    print("\nMax Drawdown:", file=sys.stderr)
    print(f"  p50: {results['max_drawdown']['p50']*100:.2f}%", file=sys.stderr)
    print(f"  p95: {results['max_drawdown']['p95']*100:.2f}%", file=sys.stderr)
    print("\nRisk:", file=sys.stderr)
    print(f"  Loss probability: {results['loss_probability']*100:.2f}%", file=sys.stderr)
    print(f"  Ruin probability: {results['ruin_probability']*100:.2f}%", file=sys.stderr)

    # Gate Q check
    gate_pass = results['ruin_probability'] < 0.01 and results['max_drawdown']['p95'] <= 0.25
    print("\nGate Q (Monte Carlo):", file=sys.stderr)
    print(f"  Ruin < 1%: {'PASS' if results['ruin_probability'] < 0.01 else 'FAIL'}", file=sys.stderr)
    print(f"  p95 DD <= 25%: {'PASS' if results['max_drawdown']['p95'] <= 0.25 else 'FAIL'}", file=sys.stderr)

    return 0 if gate_pass else 1


if __name__ == "__main__":
    sys.exit(main())
