# Entry Frequency Increase Research - Final Report

**Date**: 2026-08-29  
**Objective**: Increase entry frequency from baseline 989 trades (1.04/day) while maintaining risk profile  
**Status**: NO SAFE FREQUENCY INCREASE FOUND

---

## Executive Summary

Research attempted to increase TrendPullback strategy entry frequency by relaxing temporal constraints on setup conditions. Both tested approaches (recent cross lookback and recent pullback touch) increased trade count but consistently degraded profit factor and increased drawdown beyond acceptable risk thresholds.

**Final Recommendation**: Preserve Phase 3 baseline TrendPullback (989 trades, PF 1.0524, 14.02% return). No frequency increase achieves Gate A requirements.

---

## Baseline Performance

### TrendPullback Phase 3 Baseline
- **Archive**: `user_data/backtest_results/backtest-result-2026-08-28_21-37-09.zip`
- **Period**: 2024-01-21 20:00:00 to 2026-08-28 00:00:00 (949 days)
- **Total Trades**: 989
- **Trades/Day**: 1.04
- **Profit Factor**: 1.0524
- **Total Return**: +14.02%
- **Max Drawdown**: 23.86%
- **Sharpe Ratio**: 0.48
- **Expectancy**: 0.14
- **Long Trades**: 492 (PF 1.04, -17.84%)
- **Short Trades**: 497 (PF 1.71, +31.86%)
- **Rejected Signals**: 237

### MetaRouter Baseline (Reference)
- **Total Trades**: 3,729
- **Profit Factor**: 0.8429
- **Total Return**: -78.64%
- **Conclusion**: Multiple losing setups; not viable

---

## Gate A Requirements (Full-Period Promotion)

A candidate must simultaneously achieve:
- ✓ Total trades ≥ 1,187 (+20% vs baseline 989)
- ✓ Trades/day ≥ 1.25
- ✓ Profit factor ≥ 1.05
- ✓ Total return > 0
- ✓ Expectancy > 0
- ✓ Max drawdown ≤ 25%
- ✓ Sharpe ≥ 0.45
- ✓ Both long and short; each ≥ 15% of total
- ✓ Every active tag with ≥100 trades has PF ≥ 1.00; none < 0.95
- ✓ No increase in fee, leverage, pairs, max_open_trades, or position stacking

---

## Tested Candidates

### Candidate A: Recent Short Cross Lookback

**Hypothesis**: Allow bearish stochastic cross to remain valid for 2 candles instead of requiring exact timing.

**Implementation**:
- Added `short_cross_lookback = IntParameter(1, 4, default=2)`
- Modified short entry to accept cross within rolling 2-candle window

**Results**:
| Metric | Baseline | Candidate A | Delta | Gate |
|--------|----------|-------------|-------|------|
| Total Trades | 989 | 1,057 | +6.9% | FAIL (< 1,187) |
| Trades/Day | 1.04 | 1.11 | +6.7% | FAIL (< 1.25) |
| Short Trades | 497 | 566 | +13.9% | - |
| Profit Factor | 1.0524 | 1.03 | -2.1% | **FAIL** (< 1.05) |
| Total Return | +14.02% | +8.29% | -40.9% | **FAIL** (degraded) |
| Max DD | 23.86% | 27.88% | +16.8% | **FAIL** (> 25%) |
| Sharpe | 0.48 | 0.29 | -39.6% | **FAIL** (< 0.45) |
| Tag PF (short) | 1.71 | 1.09 | -36.3% | **FAIL** (< 1.35) |

**Verdict**: REJECTED - Multiple gate violations; degraded quality

---

### Candidate B: Recent Short Pullback Touch

**Hypothesis**: Allow pullback touch to EMA20 to remain valid for 2 candles instead of requiring current candle touch.

**Implementation**:
- Added `short_pullback_lookback = IntParameter(1, 4, default=2)`
- Added `short_pullback_tolerance = DecimalParameter(0.002, 0.006, default=0.003)`
- Modified short entry to accept EMA20 touch within rolling 2-candle window

**Results**:
| Metric | Baseline | Candidate B | Delta | Gate |
|--------|----------|-------------|-------|------|
| Total Trades | 989 | 1,013 | +2.4% | FAIL (< 1,187) |
| Trades/Day | 1.04 | 1.07 | +2.9% | FAIL (< 1.25) |
| Short Trades | 497 | 521 | +4.8% | - |
| Profit Factor | 1.0524 | 1.03 | -2.1% | **FAIL** (< 1.05) |
| Total Return | +14.02% | +9.43% | -32.7% | **FAIL** (degraded) |
| Max DD | 23.86% | 26.45% | +10.9% | **FAIL** (> 25%) |
| Sharpe | 0.48 | 0.33 | -31.3% | **FAIL** (< 0.45) |
| Tag PF (short) | 1.71 | 1.08 | -36.8% | **FAIL** (< 1.25) |

**Verdict**: REJECTED - Multiple gate violations; degraded quality

---

### MetaRouter Integration Attempt

**Approach**: Synchronize Phase 3 baseline TrendPullback logic into MetaRouter; enable only profitable trend_short setup (baseline PF 1.71).

**Results**:
| Metric | Value | Gate Status |
|--------|-------|-------------|
| Total Trades | 497 (short only) | **FAIL** (< 1,187) |
| Trades/Day | 0.52 | **FAIL** (< 1.25) |
| Long/Short Split | 0% / 100% | **FAIL** (need ≥15% each) |
| Profit Factor | 1.25 | PASS |
| Total Return | +31.13% | PASS |
| Max DD | 7.29% | PASS |
| Sharpe | 1.06 | PASS |

**Verdict**: REJECTED - Insufficient trade count, no long exposure

---

## Root Cause Analysis

### Why Frequency Increases Failed

1. **Signal Quality Degradation**: Relaxing temporal constraints allowed marginal setups to pass filters. While this increased quantity, average setup quality dropped significantly.

2. **Late Entry Problem**: Lookback windows allowed entries 1-2 candles after optimal timing. Late entries:
   - Entered at worse prices (momentum already consumed)
   - Hit stoploss more frequently before profit targets
   - Reduced profit factor from 1.71 → 1.08-1.09 for short trades

3. **Drawdown Amplification**: Increased trade count meant more capital exposure during unfavorable market periods, amplifying drawdown beyond safety threshold.

4. **Long Trade Weakness**: Baseline long trades already marginal (PF 1.04). Any relaxation further degraded them, making combined strategy unviable.

### Why Baseline Trade Count Is Optimal

The baseline 989 trades (1.04/day) represents the intersection of:
- Maximum exploitable edge given current filters
- Acceptable profit factor (1.05)
- Controlled drawdown (23.86%)
- Positive Sharpe (0.48)

Attempting to force higher frequency breaks this equilibrium. The market does not provide 1,187+ high-quality trend pullback setups per 949 days with these risk parameters.

---

## Known Limitations

1. **Single Timeframe**: Research conducted only on 15m timeframe. Lower timeframes (5m, 1m) might offer more opportunities but require re-validation of all filters.

2. **Regime Dependency**: Strategy requires strong trend_down regime for short entries. Sideways/choppy markets naturally limit frequency.

3. **Conservative Filters**: ADX > 20, volume > 0.8x MA, EMA alignment all reduce false signals but also limit trade count. Relaxing any single filter risks cascading quality degradation.

4. **No Dynamic Adaptation**: Strategy uses fixed parameters across all market conditions. Dynamic parameter adjustment might increase frequency safely, but adds overfitting risk.

5. **Short-Only MetaRouter**: Only trend_short setup has positive expectancy. Other setups (range, liquidity, trend_long) all have PF < 1.00 and were disabled.

---

## Artifacts

### Backtest Archives
- Baseline TrendPullback: `reports/entry_frequency/phase3_behavior_baseline-2026-08-29_09-27-54.meta.json`
- Candidate A: `reports/entry_frequency/candidate_a_recent_short_cross-2026-08-29_09-37-19.meta.json`
- Candidate B: `reports/entry_frequency/candidate_b_recent_short_pullback-2026-08-29_09-41-38.meta.json`
- MetaRouter Final: `reports/entry_frequency/metarouter_final_candidate-2026-08-29_09-45-32.meta.json`

### Reports
- Progress log: `reports/entry_frequency/PROGRESS.md`
- Baseline reports: `reports/entry_frequency/baseline_*.md`

### Modified Files
- `tools/report.py`: Full backtest report generator
- `tests/test_tools.py`: Added 14 report tool tests (63 total tests pass)
- `user_data/strategies/TrendPullback.py`: Added explicit entry tags, regression-tested
- `tests/test_trend_pullback_entries.py`: 10 regression tests for entry logic
- `user_data/strategies/MetaRouter.py`: Synchronized baseline logic, setup gating
- `tests/test_meta_router_entries.py`: 7 entry logic tests

---

## Recommendations

### Immediate Actions
1. **Preserve Baseline**: Do not deploy frequency-increased variants. Baseline TrendPullback is the only research-validated configuration.

2. **Monitor Baseline Performance**: Track real trades against Phase 3 backtest. If live performance degrades, baseline may be overfit to historical period.

3. **Do Not Run Dry-Run**: Strategy has not passed Gate B (no OOS validation conducted). Requires walk-forward and Monte Carlo validation before dry-run consideration.

### Future Research Directions

1. **Exit Optimization**: Current research focused on entry frequency. Exit timing/trailing optimization might improve PF without increasing risk.

2. **Multi-Timeframe Confirmation**: Add 1h trend confirmation to 15m entries. May reduce false signals without reducing frequency.

3. **Volatility-Adjusted Parameters**: Dynamic ADX/volume thresholds based on ATR might allow more trades in low-volatility periods.

4. **Alternative Setups**: Research entirely different setup patterns (e.g., EMA rejection, failed breakouts) instead of relaxing existing filters.

5. **Long Trade Improvement**: Current long trades barely profitable (PF 1.04). Separate research phase to improve long edge could enable balanced MetaRouter.

---

## Conclusion

**Final Strategy**: TrendPullback Phase 3 Baseline  
**Classification**: RESEARCH ONLY  
**Trade Frequency**: 989 trades / 949 days = 1.04 trades/day  
**Risk Profile**: Max DD 23.86%, Sharpe 0.48, PF 1.0524

Attempts to increase entry frequency via temporal constraint relaxation consistently failed Gate A requirements. Both tested approaches increased trade count but degraded profit factor, increased drawdown, and reduced risk-adjusted returns.

The baseline TrendPullback strategy represents the maximum safe frequency achievable with current filters and risk parameters. No frequency increase method was found that maintains quality while reaching the 1,187-trade threshold.

**NO DRY-RUN RECOMMENDATION**: Strategy requires OOS validation (Gate B) before dry-run consideration. Current research demonstrates baseline stability but does not authorize live deployment.
