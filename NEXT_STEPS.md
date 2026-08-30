# Next Steps and Recommendations

**For:** Tam (project owner)  
**Generated:** 2026-08-29T12:12:00Z  
**Context:** Pro hardening session complete - measurement tools fixed, baseline issues documented

---

## Immediate Actions (Before Any Trading)

### 1. Review the Findings
Read in order:
1. `reports/pro_hardening/FINAL.md` - Complete analysis and verdict
2. `reports/pro_hardening/ERRATA.md` - What was wrong in old reports
3. `reports/pro_hardening/PROGRESS.md` - What was done phase by phase

**Key takeaway:** Your baseline strategy (TrendPullback) is NOT stable. 2026 is a losing year.

### 2. Update .gitignore
```bash
echo "*.sqlite*" >> .gitignore
echo "*.db*" >> .gitignore
echo "*.log" >> .gitignore
```

These files are currently untracked but should be ignored.

### 3. Verify Tests Still Pass
```bash
.venv/Scripts/python.exe -m pytest tests/ -v
```
Should show: 85 passed

---

## If Continuing Research (20-40 hours)

### Phase 8: New Strategy Research (2-4 hours)
**Why:** Current baseline long side is failing. Need short-only or fundamentally different approach.

```bash
# Create new strategy file
cp user_data/strategies/TrendPullback.py user_data/strategies/RobustTrend.py

# Focus on short-only first (long side has been losing)
# Use MetaRouter trend_short as starting point (PF 1.26)
```

**Research candidates (from plan):**
- R0: MetaRouter trend_short (baseline, re-run with fixed measurement)
- R1: R0 + DMI directional separation
- R2: R1 + EMA slope / ATR normalized
- R3: R1 + regime persistence (2-3 candles)

**Selection criteria:**
- Keep candidate matrix small (max 5 candidates)
- Each differs by ONE hypothesis only
- Unit tests for each signal trigger
- Max 6 hyperopt parameters

### Phase 9: Lock Temporal Splits (30 minutes)
**Critical:** Lock these BEFORE running hyperopt, never look at holdout until final.

```bash
# Create experiment spec
cat > reports/pro_hardening/EXPERIMENT_SPEC.md << 'EOF'
# Experiment: Short-Only Strategy Research

## Temporal Splits (LOCKED)
- Development/train: 2024-01-01 to 2025-06-30
- Validation: 2025-07-01 to 2025-12-31  
- Final holdout: 2026-01-01 to 2026-08-28

## Walk-Forward
- 6 folds, expanding window
- Test window: 90 days minimum
- Embargo: 100 candles @ 15m = ~5 days

SHA256 of this spec: [calculate after writing]
EOF

# Hash it
sha256sum reports/pro_hardening/EXPERIMENT_SPEC.md
```

### Phase 10: Hyperopt Multi-Seed (2-4 hours runtime)
**Only for candidates that pass screening.**

```bash
# Run for best 2 candidates from Phase 8
python -m tools.walkforward \
  --strategy RobustTrend \
  --config user_data/config/config.backtest.json \
  --timerange 20240101-20250630 \
  --folds 3 \
  --epochs 200 \
  --random-state 42 \
  --enable-protections

# Repeat with seeds: 1337, 20260829
# Pick parameter by median validation score across seeds
```

### Phase 11: Validation Suite (1-2 hours)
For winner from Phase 10:

```bash
# Lookahead analysis
rtk .venv/Scripts/freqtrade.exe lookahead-analysis \
  -c user_data/config/config.backtest.json \
  -s RobustTrend \
  --timerange 20240101-20260828

# Recursive analysis  
rtk .venv/Scripts/freqtrade.exe recursive-analysis \
  -c user_data/config/config.backtest.json \
  -s RobustTrend \
  --timerange 20240101-20260828

# Cost stress test
# Run backtest with increasing fee assumptions
# 0.1%, 0.2%, 0.4%, 0.6%
```

### Phase 12: Full Walk-Forward (2-5 hours runtime)
```bash
python -m tools.walkforward \
  --strategy RobustTrend \
  --config user_data/config/config.backtest.json \
  --timerange 20240101-20260828 \
  --folds 6 \
  --is-months 12 \
  --oos-months 3 \
  --epochs 300 \
  --random-state 42 \
  --enable-protections \
  --output-dir reports/walkforward_robust_trend

# Then Monte Carlo on OOS results
python -m tools.montecarlo \
  --daily-returns reports/walkforward_robust_trend/.../daily_returns.json \
  --n-paths 10000 \
  --seed 42 \
  --block-size 7
```

### Phase 13: Operational Readiness (2-4 hours)
Build the missing tools:

```python
# tools/healthcheck.py
# - Check: process running, code hash matches, data fresh, config valid
# - Check: risk state file readable, no halt active
# - Check: disk space, DB lock, clock skew
# - Output: JSON + exit code

# tools/reconcile_dryrun.py  
# - Compare: expected signals (from closed candles) vs DB trades
# - Classify: executed, blocked-by-guard, rejected, missed, duplicate
# - Report: reconciliation gaps with timestamps

# Implement persistent risk state
# - File: .risk_state.json with daily/weekly PnL, peak equity, halt status
# - Atomic writes: temp + rename
# - UTC timestamps
# - Test: restart preserves halt
```

### Phase 14: Final Verification
Only if all above pass:
1. All tests pass (should be 85+)
2. Gate Q requirements met on holdout
3. Gate S gaps fixed (persistence, CI)
4. Gate O tools built (healthcheck, reconcile)
5. Documentation complete

Then verdict can upgrade from `RESEARCH ONLY` to `READY FOR DRY-RUN REVIEW`.

---

## If Not Continuing (Current State)

### What You Have Now
**Working measurement tools:**
- `python -m tools.report` - Accurate performance reports with provenance
- `python -m tools.walkforward` - Proper OOS validation with daily equity
- `python -m tools.montecarlo` - Block bootstrap risk assessment

**85 passing tests** - All measurement infrastructure validated

**Corrected understanding:**
- Baseline is NOT stable (2026 PF 0.81 < 1.0)
- Long side losing overall (-17.84%)
- Short side carried entire strategy (+31.86%)
- Clear temporal decay: 2024 > 2025 > 2026

### What You Don't Have
- No validated trading candidate (Gate Q not passed)
- Risk state not persistent (Gate S partial fail)
- No CI/healthcheck/reconciliation tools (Gate O not assessed)
- No dry-run authorization

### Safe Next Steps
1. Use the fixed tools to research new strategies
2. Start with short-only (avoid failed long side)
3. Use small candidate matrix (5 max)
4. Lock temporal splits before optimization
5. Never look at holdout until validation complete

### Unsafe Actions
❌ Do NOT deploy current baseline (TrendPullback) - it's failing in 2026  
❌ Do NOT trust old reports - they had schema errors  
❌ Do NOT skip validation phases - measurement alone is not enough  
❌ Do NOT dry-run without persistent risk state  
❌ Do NOT live-trade without 30-day dry-run soak

---

## Cost Estimates

### Time Investment
- **Measurement hardening (done):** ~2.5 hours
- **Strategy research (Phases 8-12):** 15-30 hours
  - Research: 2-4 hours
  - Hyperopt: 2-4 hours runtime
  - Validation: 1-2 hours
  - Walk-forward: 2-5 hours runtime
  - Analysis: 2-4 hours
- **Operational tooling (Phase 13):** 2-4 hours
- **Total to deployment-ready:** 20-40 hours

### Compute Cost
- Hyperopt (3 seeds × 200 epochs): ~2 hours CPU
- Walk-forward (6 folds × 300 epochs): ~4 hours CPU  
- Monte Carlo (10k paths): ~1 minute
- **Total compute:** ~6-8 hours continuous

### Risk of Continuing with Current Baseline
**Very high** - 2026 is actively losing. Deploying without fixing the strategy would likely lose money immediately.

---

## Questions to Answer Before Continuing

1. **Do you want to continue research?**
   - Yes → Follow Phase 8-14 plan (20-40 hours)
   - No → Use tools for future research when ready

2. **What's your risk tolerance?**
   - Conservative → Wait for robust short-only candidate
   - Aggressive → Could try MetaRouter short-only (but no OOS validation yet)

3. **What's your time availability?**
   - < 5 hours → Don't start, tools are ready when you are
   - 20-40 hours → Can complete full validation
   - > 40 hours → Can include operational tooling and dry-run

4. **What's your goal?**
   - Learn/research → Current tools are sufficient
   - Paper trade → Need Phase 13 tooling first
   - Live trade → Need ALL phases + 30-day soak

---

## Critical Warnings

⚠️ **DO NOT DEPLOY TRENDPULLBACK** - Temporal decay confirmed, 2026 losing year

⚠️ **OLD REPORTS INVALID** - Schema errors corrected, numbers were wrong

⚠️ **LONG SIDE FAILING** - PF 0.88 overall, avoid long-only or balanced strategies

⚠️ **NO CANDIDATE READY** - Nothing has passed Gate Q validation yet

⚠️ **OPERATIONAL GAPS** - Risk state not persistent, no healthcheck, no CI

---

## Summary

**You asked me to harden the system. I did the measurement layer.**

✓ Fixed: Report parser, walk-forward, Monte Carlo  
✓ Found: Baseline temporal decay, schema errors, long-side failure  
✓ Delivered: 85 tests, corrected reports, clear documentation  

✗ Not done: Strategy validation, operational tooling (20-40 more hours)  
✗ Verdict: RESEARCH ONLY (not deployment-ready)

**The tools are reliable. The strategy is not.**

Use the tools to research a better strategy, or wait until you have 20-40 hours for full validation pipeline.
