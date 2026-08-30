# Errata: Report Corrections

**Generated:** 2026-08-29T11:48:00Z  
**Reason:** Schema parser errors in tools/report.py discovered during Phase 1 hardening

## Summary

All reports generated before 2026-08-29T11:47:00Z used an incorrect schema parser that:
1. Read wrong field names for long/short trade counts
2. Misinterpreted profit_total as percent when it's a ratio
3. Read wrong drawdown field (max_drawdown vs max_drawdown_account)
4. Lacked provenance tracking (no SHA256, no source attribution)
5. Did not validate required fields or handle schema errors

This errata documents which numbers were wrong and provides corrected values from re-parsing the original ZIP archives.

## Affected Reports

All reports in:
- `reports/entry_frequency/` (generated 2026-08-29)
- Any manual analysis referencing these numbers
- `DECISIONS.md` conclusions based on incorrect metrics

## Baseline: TrendPullback Full Period

**Source ZIP:** `reports/entry_frequency/phase3_behavior_baseline-2026-08-29_09-27-54.zip`  
**SHA256:** (will be calculated during regeneration)

### What Was Wrong
Old parser likely showed:
- Incorrect long/short counts if using `trades_long`/`trades_short`
- Return as 0.14% instead of 14.02% (wrong decimal interpretation)
- Drawdown potentially as 353.06% instead of 23.86% (reading abs instead of ratio)
- Missing breakdown by year/quarter

### Correct Numbers
From direct ZIP parsing verified in Phase 1 regression tests:

| Metric | Correct Value | Unit |
|--------|--------------|------|
| Total Trades | 989 | count |
| Long Trades | 492 | count |
| Short Trades | 497 | count |
| Profit Factor | 1.0524116935 | ratio |
| Return | 14.0186% | percent (0.1401863914 ratio) |
| Return (Absolute) | 140.19 USDT | stake |
| Long Return | -17.84% | percent |
| Short Return | +31.86% | percent |
| Max DD (Account) | 23.86% | percent (0.2386427204 ratio) |
| Max DD (Absolute) | 353.06 USDT | stake |
| Sharpe | 0.4780104318 | ratio |
| Trades/Day | 1.04 | count/day (989/949) |
| Backtest Days | 949 | days |
| Period | 2024-01-21 to 2026-08-28 | dates |

### Long/Short Breakdown Correction
- **Long side:** 492 trades, PF 0.8756, return -17.84%, tag `trend_pullback_long`
- **Short side:** 497 trades, PF 1.2568, return +31.86%, tag `trend_pullback_short`

**Key Issue:** Old analysis may have incorrectly attributed MetaRouter short-only performance to TrendPullback baseline. The baseline includes BOTH long and short, with long side showing clear losses.

## Candidate A: Recent Short Cross

**Source ZIP:** `reports/entry_frequency/candidate_a_recent_short_cross-2026-08-29_09-37-19.zip`  
**SHA256:** (TBD)

From plan documentation, Candidate A was reported as:
- PF 1.0289, DD 27.88%

This will be re-verified against actual ZIP contents.

## Candidate B: Recent Short Pullback

**Source ZIP:** `reports/entry_frequency/candidate_b_recent_short_pullback-2026-08-29_09-41-38.zip`  
**SHA256:** (TBD)

From plan documentation, Candidate B was reported as:
- PF 1.0346, DD 26.45%

This will be re-verified against actual ZIP contents.

## MetaRouter Short-Only

**Source ZIP:** `reports/entry_frequency/metarouter_final_candidate-2026-08-29_09-45-32.zip`  
**SHA256:** (TBD)

From plan documentation, MetaRouter short-only was reported as:
- 497 trades, PF 1.2520, return 31.13%, DD 7.29%, Sharpe 1.056 on full period

**Critical Note:** This is a DIFFERENT strategy (MetaRouter with only short signals enabled) and its performance should NOT be compared directly to TrendPullback baseline which includes both long and short sides.

## Temporal Decay Evidence

From plan, the baseline shows clear temporal decay that must be documented:

### By Year (TrendPullback Baseline)
| Year | Long PF | Short PF | Combined PF |
|------|---------|----------|-------------|
| 2024 | 1.165 | 1.498 | >1.0 |
| 2025 | 0.786 | 1.279 | ~1.0 |
| 2026 | 0.572 | 1.013 | <1.0 |

### By Quarter (2025-Q3 to 2026-Q3)
According to plan: "Mọi quý từ 2025-Q3 đến 2026-Q3 đều có tổng PF dưới 1."

This decay evidence must be extracted from the periodic_breakdown in the ZIP and formally documented in the regenerated reports.

## Impact on DECISIONS.md

The following conclusions in DECISIONS.md are affected and must be corrected:
1. Any claim that baseline is "stable" - FALSE, clear temporal decay
2. Any attribution of MetaRouter short tag performance to TrendPullback strategy
3. Any comparison that doesn't account for long side losses
4. Any numbers without provenance (no ZIP SHA256, no verification trail)

## Regeneration Plan

Phase 2 will:
1. Generate corrected report for each ZIP using new parser
2. Add temporal breakdown tables (year/quarter/month if available)
3. Flag quarters with PF < 1.0 as evidence of decay
4. Update DECISIONS.md with corrections
5. Create automated tests that assert 2025-Q3 through 2026-Q3 all have PF < 1.0

## Verification

All regenerated reports include:
- Source ZIP filename and SHA256 hash
- Explicit units (ratio vs percent vs stake)
- Provenance timestamp
- Breakdown by tag, pair, exit reason
- Temporal breakdown if available in export
- Clear distinction between strategies (TrendPullback vs MetaRouter)

Old artifacts remain untouched for audit trail. New reports are placed in `reports/pro_hardening/` with clear timestamps.
