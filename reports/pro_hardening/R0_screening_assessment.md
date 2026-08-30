# R0 Candidate Screening Assessment

**Candidate:** RobustTrend R0 (MetaRouter trend_short baseline)  
**Date:** 2026-08-29  
**Experiment:** PRO-HARDENING-001

---

## Full Period Results (2024-01-01 to 2026-08-28)

**Source:** `backtest-result-2026-08-29_13-22-48.zip`  
**SHA256:** `4a6878c7fb76b12f5c546ef3c9a7559e5b1c89cf5e70d524570143088dd351ab`

| Metric | Value | Gate Q Threshold | Pass? |
|--------|-------|------------------|-------|
| Trades | 499 | >= 450 | ✓ PASS |
| Profit Factor | 1.3646 | >= 1.15 | ✓ PASS |
| Return | 44.08% | > 0 | ✓ PASS |
| Expectancy | 0.8833 | > 0 | ✓ PASS |
| Max DD (Account) | 6.94% | <= 15% | ✓ PASS |
| Daily Sharpe | 1.4584 | >= 0.75 | ✓ PASS |

### Side Breakdown
- Long: 0 trades (N/A - short-only strategy)
- Short: 499 trades, PF 1.3646, Return 44.08%

### Pair Breakdown
| Pair | Trades | PF | Return % |
|------|--------|----|---------:|
| AVAX/USDT | 115 | 1.5290 | 14.04% |
| LINK/USDT | 98 | 1.5751 | 12.56% |
| SOL/USDT | 100 | 1.5371 | 12.29% |
| ETH/USDT | 100 | 1.2865 | 7.51% |
| BTC/USDT | 86 | 0.9009 | -2.32% |

**CONCERN:** BTC pair PF 0.9009 < 0.90 barely passes threshold with 86 trades.

### Temporal Breakdown
| Year | Trades | PF | Observation |
|------|--------|----|----|
| 2024 | 166 | 1.7153 | Strong |
| 2025 | 205 | 1.3992 | Declining |
| 2026 | 128 | 1.0755 | Weak |

**OBSERVATION:** Clear temporal decay pattern continues.

---

## Recent Period Results (2026-01-01 to 2026-08-28)

**Source:** `backtest-result-2026-08-29_13-30-15.zip`  
**SHA256:** `dac0673da5dfaf81160978a249a27a4101733bde17b191688dfaab658ae6cd39`

| Metric | Value | Gate Q Threshold | Pass? |
|--------|-------|------------------|-------|
| Trades | 128 | >= 100 | ✓ PASS |
| Profit Factor | 1.0914 | >= 1.10 | ✗ **FAIL** |
| Return | 2.56% | > 0 | ✓ PASS |
| Max DD (Account) | 6.72% | <= 12% | ✓ PASS |

### Recent Pair Breakdown
| Pair | Trades | PF | Return % |
|------|--------|----|---------:|
| SOL/USDT | 27 | 1.3276 | 1.71% |
| ETH/USDT | 25 | 1.1953 | 1.10% |
| LINK/USDT | 21 | 1.1489 | 0.66% |
| AVAX/USDT | 30 | 1.0604 | 0.41% |
| BTC/USDT | 25 | 0.7752 | -1.33% |

**CRITICAL:** BTC pair PF 0.7752 << 0.90 with 25 trades.

---

## Gate Q Screening Verdict

### ✗ FAIL - Recent Period

**Failure reason:** Profit Factor 1.0914 < 1.10 (required >= 1.10)

**Additional concerns:**
1. BTC pair consistently underperforms (PF 0.90 full, 0.78 recent)
2. Temporal decay pattern continues (2024: 1.72 → 2025: 1.40 → 2026: 1.09)
3. Recent Sharpe 0.43 is well below full-period 1.46 (degrading edge)

### Decision

**DO NOT PROCEED** to expensive validation (Hyperopt, Walk-Forward, Monte Carlo).

Per EXPERIMENT_SPEC.md screening rules:
> "Candidate failing Gate Q screening (full period OR recent) is dropped immediately"

R0 fails recent period PF threshold. This candidate is **REJECTED**.

---

## Analysis

### Why R0 Failed

1. **No additional filters:** Raw MetaRouter trend_short without DMI/slope/persistence
2. **BTC pair drag:** Consistently losing on BTC (-2.32% full, -1.33% recent)
3. **Temporal decay:** Edge degrades over time, recent PF barely profitable
4. **Market regime shift:** 2026 conditions less favorable for simple pullback shorts

### Hypothesis for R1

Adding DMI directional filter (`-DI > +DI`) should:
- Remove weak signals when directional movement unclear
- Reduce BTC pair losses (choppy trending)
- Improve recent period robustness

---

## Next Steps

1. ✓ R0 documented and rejected
2. → Create R1 candidate (R0 + DMI filter)
3. → Screen R1 on full + recent periods
4. → If R1 fails, continue to R2/R3 per candidate matrix
5. → If all candidates fail, verdict: `NO ROBUST CANDIDATE`

---

## Artifacts

- Full period report: `reports/pro_hardening/R0_full_period_20260829_062914.md`
- Recent period report: `reports/pro_hardening/R0_recent_2026.md`
- Full backtest: `user_data/backtest_results/backtest-result-2026-08-29_13-22-48.zip`
- Recent backtest: `user_data/backtest_results/backtest-result-2026-08-29_13-30-15.zip`
