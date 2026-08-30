#!/usr/bin/env python3
"""
Market Regime Analysis Tool
Analyzes why strategy performance changed in Jul-Aug 2026
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json

def analyze_market_regime(data_dir: Path, pairs: list, start_date: str, end_date: str):
    """
    Analyze market characteristics across different time periods
    """
    results = {}

    for pair in pairs:
        # Read 15m data
        file_path = data_dir / f"{pair.replace('/', '_').replace(':', '_')}-15m-futures.feather"

        if not file_path.exists():
            print(f"⚠️ Data file not found: {file_path}")
            continue

        df = pd.read_feather(file_path)
        df['date'] = pd.to_datetime(df['date'])

        # Filter to analysis period
        mask = (df['date'] >= start_date) & (df['date'] <= end_date)
        period_data = df[mask].copy()

        if len(period_data) == 0:
            print(f"⚠️ No data for {pair} in period {start_date} to {end_date}")
            continue

        # Calculate key metrics
        metrics = {}

        # 1. Trend Analysis
        period_data['returns'] = period_data['close'].pct_change()
        metrics['avg_return'] = period_data['returns'].mean()
        metrics['volatility'] = period_data['returns'].std()
        metrics['total_return'] = ((period_data['close'].iloc[-1] / period_data['close'].iloc[0]) - 1) * 100

        # 2. Volume Analysis
        metrics['avg_volume'] = period_data['volume'].mean()
        metrics['volume_std'] = period_data['volume'].std()
        metrics['volume_trend'] = period_data['volume'].iloc[-1] / period_data['volume'].iloc[0]

        # 3. Range Analysis (for trend detection)
        period_data['high_low_range'] = (period_data['high'] - period_data['low']) / period_data['close']
        metrics['avg_range_pct'] = period_data['high_low_range'].mean() * 100

        # 4. Directional Movement
        period_data['higher_high'] = period_data['high'] > period_data['high'].shift(1)
        period_data['lower_low'] = period_data['low'] < period_data['low'].shift(1)

        up_moves = period_data['higher_high'].sum()
        down_moves = period_data['lower_low'].sum()

        metrics['up_days_pct'] = (up_moves / len(period_data)) * 100
        metrics['down_days_pct'] = (down_moves / len(period_data)) * 100

        # 5. Trend Strength (simple EMA-based)
        period_data['ema20'] = period_data['close'].ewm(span=20, adjust=False).mean()
        period_data['ema50'] = period_data['close'].ewm(span=50, adjust=False).mean()

        # Count trend days
        trend_up_days = (period_data['close'] > period_data['ema20']).sum()
        trend_down_days = (period_data['close'] < period_data['ema20']).sum()

        metrics['above_ema20_pct'] = (trend_up_days / len(period_data)) * 100
        metrics['below_ema20_pct'] = (trend_down_days / len(period_data)) * 100

        # 6. Price Action (for shorts)
        # Check if market had clear downtrends (good for short strategy)
        period_data['is_downtrend'] = (period_data['ema20'] < period_data['ema50']) & \
                                       (period_data['close'] < period_data['ema20'])
        metrics['downtrend_days_pct'] = (period_data['is_downtrend'].sum() / len(period_data)) * 100

        results[pair] = metrics

    return results

def compare_periods(good_period_results, bad_period_results):
    """
    Compare characteristics between good and bad performance periods
    """
    print("\n" + "="*80)
    print("MARKET REGIME COMPARISON")
    print("="*80)

    for pair in good_period_results.keys():
        if pair not in bad_period_results:
            continue

        print(f"\n{pair}")
        print("-" * 80)

        good = good_period_results[pair]
        bad = bad_period_results[pair]

        comparisons = [
            ("Total Return", good['total_return'], bad['total_return'], '%', True),
            ("Volatility", good['volatility'], bad['volatility'], '', False),
            ("Avg Range", good['avg_range_pct'], bad['avg_range_pct'], '%', False),
            ("Down Days", good['down_days_pct'], bad['down_days_pct'], '%', True),
            ("Below EMA20", good['below_ema20_pct'], bad['below_ema20_pct'], '%', True),
            ("Downtrend Days", good['downtrend_days_pct'], bad['downtrend_days_pct'], '%', True),
        ]

        for metric_name, good_val, bad_val, unit, higher_better in comparisons:
            change = bad_val - good_val
            change_pct = (change / abs(good_val)) * 100 if good_val != 0 else 0

            if higher_better:
                status = "[OK]" if bad_val > good_val else "[BAD]"
            else:
                status = "[CHG]"

            print(f"{metric_name:20} | Good: {good_val:8.2f}{unit:3} | Bad: {bad_val:8.2f}{unit:3} | "
                  f"Change: {change:+8.2f}{unit:3} ({change_pct:+6.1f}%) {status}")

def main():
    print("Market Regime Analysis - Jul-Aug 2026 vs Jun 2026")
    print("="*80)

    data_dir = Path("user_data/data/binance/futures")
    pairs = ["ETH_USDT_USDT", "SOL_USDT_USDT", "AVAX_USDT_USDT", "LINK_USDT_USDT"]

    # Good period: June 2026 (72% win rate, +59 USDT)
    print("\nAnalyzing GOOD period: June 2026")
    good_period = analyze_market_regime(data_dir, pairs, "2026-06-01", "2026-06-30")

    # Bad period: Jul-Aug 2026 (20% and 43% win rate, losses)
    print("\nAnalyzing BAD period: Jul-Aug 2026")
    bad_period = analyze_market_regime(data_dir, pairs, "2026-07-01", "2026-08-28")

    # Compare
    compare_periods(good_period, bad_period)

    # Overall assessment
    print("\n" + "="*80)
    print("KEY FINDINGS")
    print("="*80)

    # Calculate aggregate changes
    all_pairs = list(good_period.keys())

    if len(all_pairs) > 0:
        avg_return_good = np.mean([good_period[p]['total_return'] for p in all_pairs])
        avg_return_bad = np.mean([bad_period[p]['total_return'] for p in all_pairs])

        avg_downtrend_good = np.mean([good_period[p]['downtrend_days_pct'] for p in all_pairs])
        avg_downtrend_bad = np.mean([bad_period[p]['downtrend_days_pct'] for p in all_pairs])

        avg_vol_good = np.mean([good_period[p]['volatility'] for p in all_pairs])
        avg_vol_bad = np.mean([bad_period[p]['volatility'] for p in all_pairs])

        print(f"\n[*] Market Direction:")
        print(f"   Good period avg return: {avg_return_good:+.2f}%")
        print(f"   Bad period avg return:  {avg_return_bad:+.2f}%")
        print(f"   -> Market shifted {'UP' if avg_return_bad > avg_return_good else 'DOWN'}")

        print(f"\n[*] Downtrend Opportunities (for short strategy):")
        print(f"   Good period: {avg_downtrend_good:.1f}% of days in clear downtrend")
        print(f"   Bad period:  {avg_downtrend_bad:.1f}% of days in clear downtrend")

        if avg_downtrend_bad < avg_downtrend_good * 0.7:
            print(f"   [!] CRITICAL: {((1 - avg_downtrend_bad/avg_downtrend_good) * 100):.0f}% fewer downtrend opportunities!")
            print(f"   -> Short strategy has fewer valid setups")

        print(f"\n[*] Volatility:")
        print(f"   Good period: {avg_vol_good:.6f}")
        print(f"   Bad period:  {avg_vol_bad:.6f}")

        vol_change = ((avg_vol_bad / avg_vol_good) - 1) * 100
        if abs(vol_change) > 20:
            print(f"   [!] Volatility changed by {vol_change:+.1f}% - significant regime shift")

    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)

    print("\n1. If downtrend days decreased significantly:")
    print("   -> Market regime shifted away from trending down")
    print("   -> Short-only strategy naturally struggles")
    print("   -> Consider: Wait for regime to shift back OR add regime filter")

    print("\n2. If volatility changed significantly:")
    print("   -> Stop loss / take profit levels may need adjustment")
    print("   -> Consider: Re-optimize SL/TP for current volatility")

    print("\n3. If market shifted to ranging/choppy:")
    print("   -> Trend-following strategy gets whipsawed")
    print("   -> Consider: Add ADX filter (only trade when ADX > 25)")

    print("\n" + "="*80)

if __name__ == "__main__":
    main()
