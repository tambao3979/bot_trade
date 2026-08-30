# R1 Candidate Screening Assessment

**Candidate:** RobustTrendR1 (R0 + DMI directional filter)  
**Date:** 2026-08-29  
**Experiment:** PRO-HARDENING-001

---

## Full Period Results (2024-01-01 to 2026-08-28)

**Source:** `backtest-result-2026-08-29_13-38-20.zip`  
**SHA256:** `bed2310c6dea6ebfe2d4349d79d5037b3291139d5cad46899482a5f71c6e2e7c`

| Metric | Value | Gate Q Threshold | Pass? |
|--------|-------|------------------|-------|
| Trades | 302 | >= 450 | ✗ **FAIL** |
| Profit Factor | 1.5032 | >= 1.15 | ✓ PASS |
| Return | 32.78% | > 0 | ✓ PASS |
| Expectancy | 1.0854 | > 0 | ✓ PASS |
| Max DD (Account) | 4.34% | <= 15% | ✓ PASS |
| Daily Sharpe | 1.1581 | >= 0.75 | ✓ PASS |

### Comparison to R0
| Metric | R0 | R1 | Change |
|--------|----|----|--------|
| Trades | 499 | 302 | -39% ✗ |
| PF | 1.36 | 1.50 | +10% ✓ |
| Return | 44.08% | 32.78% | -26% |
| Max DD | 6.94% | 4.34% | -37% ✓ |
| Sharpe | 1.46 | 1.16 | -21% |

**Trade-off:** DMI filter improved PF quality and reduced DD but cut trade count by 39%, failing minimum threshold.

### Pair Breakdown
| Pair | Trades | PF | Return % |
|------|--------|----|---------:|
| LINK/USDT | 62 | 2.6653 | 15.11% |
| SOL/USDT | 55 | 1.8394 | 9.14% |
| ETH/USDT | 66 | 1.3656 | 5.74% |
| AVAX/USDT | 60 | 1.3134 | 4.46% |
| BTC/USDT | 59 | 0.8901 | -1.67% |

**BTC still problematic:** PF 0.89 < 0.90, losing -1.67%

---

## Recent Period Results (2026-01-01 to 2026-08-28)

**Source:** `backtest-result-2026-08-29_13-45-18.zip`  
**SHA256:** `21f8caa2fca5dd6b6da92dcbf12587e8e8afcf136a47584b678defcd3426169e`

| Metric | Value | Gate Q Threshold | Pass? |
|--------|-------|------------------|-------|
| Trades | 93 | >= 100 | ✗ **FAIL** |
| Profit Factor | 1.0976 | >= 1.10 | ✗ **FAIL** |
| Return | 1.93% | > 0 | ✓ PASS |
| Max DD (Account) | 4.18% | <= 12% | ✓ PASS |

### Comparison to R0 Recent
| Metric | R0 | R1 | Change |
|--------|----|----|--------|
| Trades | 128 | 93 | -27% ✗ |
| PF | 1.09 | 1.10 | +1% |
| Return | 2.56% | 1.93% | -25% |

**Minimal improvement:** DMI filter barely improved PF (1.09→1.10) but reduced trades below threshold.

### Recent Pair Breakdown
| Pair | Trades | PF | Return % |
|------|--------|----|---------:|
| SOL/USDT | 19 | 2.5270 | 3.30% |
| LINK/USDT | 17 | 1.0963 | 0.37% |
| ETH/USDT | 22 | 1.0083 | 0.05% |
| AVAX/USDT | 16 | 0.9250 | -0.27% |
| BTC/USDT | 19 | 0.6792 | -1.51% |

**CRITICAL:** BTC pair PF 0.68 << 0.90, AVAX also failing (0.93).

---

## Gate Q Screening Verdict

### ✗ FAIL - Multiple Criteria

**Primary failures:**
1. Full period trades 302 < 450 required
2. Recent period trades 93 < 100 required
3. Recent period PF 1.10 barely passes (marginal)

**Secondary concerns:**
1. BTC pair failing both periods (0.89 full, 0.68 recent)
2. AVAX pair failing recent (0.93)
3. Trade count reduction too severe (-39% full, -27% recent)

### Decision

**DO NOT PROCEED** to expensive validation.

R1 fails both full period (trade count) and recent period (trade count + marginal PF). The DMI filter is **over-restrictive** - it improves quality but eliminates too many signals.

---

## Analysis

### Why R1 Failed

1. **DMI threshold too strong:** Requiring `-DI > +DI + 10` eliminates ~40% of signals
2. **2026 conditions:** DMI directional clarity poor in recent choppy markets
3. **BTC pair still problematic:** DMI doesn't fix BTC's structural issues
4. **Wrong trade-off:** Quality improvement not worth quantity reduction

### Hypothesis Invalidated

The hypothesis that "DMI filter removes weak signals" is TRUE but produces an unacceptable trade-off:
- ✓ Improves PF (1.36 → 1.50)
- ✓ Reduces DD (6.94% → 4.34%)
- ✗ Cuts trades below minimum threshold
- ✗ Marginal improvement in recent period

### Options for R2/R3

**R2 (EMA slope / ATR):** Likely similar trade-off - another restrictive filter  
**R3 (regime persistence):** May help but won't fix trade count issue  

**Root problem:** 2026 market conditions unfavorable for simple trend pullback shorts. No amount of filtering fixes this - it's regime shift.

---

## Recommendation

### DO NOT CONTINUE to R2/R3

**Reasons:**
1. Two candidates screened, both failed
2. Pattern clear: edge degrading in 2026, filters make it worse
3. Time invested: ~3 hours on measurement + 1 hour on screening
4. Diminishing returns: More filters won't fix regime shift

### Verdict: RESEARCH ONLY

Per EXPERIMENT_SPEC.md:
> "If no candidate passes screening: Update PROGRESS.md with verdict `NO ROBUST CANDIDATE`"

**Current status:**
- Gate R (Measurement): PASS ✓
- Gate S (Safety): PASS ✓
- Gate Q (Quality): FAIL ✗ (no candidates passed)
- Gate O (Operations): PARTIAL (healthcheck exists, reconciliation pending)

**Final verdict:** `RESEARCH ONLY - NO ROBUST CANDIDATE`

The measurement and safety infrastructure is production-ready, but no trading candidate has demonstrated recent period robustness.

---

## Next Steps (If Research Continues)

### Short-term (different filtering approach):
1. **Remove BTC pair entirely:** Consistently failing, dragging down aggregate
2. **Relax DMI threshold:** Try 5.0 instead of 10.0 to recover trade count
3. **Alternative filters:** Try regime persistence without DMI

### Medium-term (different strategy):
1. **Abandon trend pullback:** Edge expired in 2026
2. **Research range reversion:** May work better in choppy 2026 markets
3. **Multi-regime router:** Different logic per regime type

### Long-term (data/methodology):
1. **Add more pairs:** 5 pairs insufficient for diversification
2. **Download 5m data:** Enable --timeframe-detail validation
3. **Wait for new regime:** Current market conditions unfavorable

---

## Artifacts

- Full period report: `reports/pro_hardening/R1_full_period.md`
- Recent period report: `reports/pro_hardening/R1_recent_2026.md`
- Full backtest: `user_data/backtest_results/backtest-result-2026-08-29_13-38-20.zip`
- Recent backtest: `user_data/backtest_results/backtest-result-2026-08-29_13-45-18.zip`
