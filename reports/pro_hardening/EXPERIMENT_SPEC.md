# Experiment Specification: Short-Only Strategy Research

**Experiment ID:** PRO-HARDENING-001  
**Created:** 2026-08-29T06:20:00Z  
**Status:** LOCKED  

> **IMPORTANT:** This specification is LOCKED before optimization begins. Do NOT modify temporal splits or gate thresholds after hyperopt starts. If validation fails on holdout, the experiment fails - do not adjust splits retroactively.

---

## Temporal Splits (LOCKED)

### Development/Train Period
- **Start:** 2024-01-01
- **End:** 2025-06-30
- **Purpose:** Hyperopt parameter tuning, initial screening
- **Duration:** 18 months

### Validation Period  
- **Start:** 2025-07-01
- **End:** 2025-12-31
- **Purpose:** Multi-seed parameter selection, stability checks
- **Duration:** 6 months

### Final Holdout Period
- **Start:** 2026-01-01
- **End:** 2026-08-28
- **Purpose:** Final OOS validation (NEVER used for tuning)
- **Duration:** 8 months

### Walk-Forward Configuration
- **Folds:** 6
- **Type:** Expanding window
- **Test window:** 90 days minimum
- **Embargo:** 100 candles × 15m = ~5 days
- **Train/Test split:** No overlap after embargo

**Hash of this spec:**
```
# Generate after writing
sha256sum reports/pro_hardening/EXPERIMENT_SPEC.md
```

---

## Research Thesis

**Problem:** TrendPullback baseline shows severe temporal decay:
- 2024: PF 1.29 (healthy)
- 2025: PF 1.03 (barely profitable)
- 2026: PF 0.81 (losing)

**Root cause:** Long side failure:
- Long: 492 trades, PF 0.88, return -17.84%
- Short: 497 trades, PF 1.26, return +31.86%

**Strategy:** Focus on short-only first. Only consider long if it independently passes Gate Q.

---

## Candidate Matrix

Each candidate differs by ONE hypothesis from the previous. Maximum 5-6 candidates.

### R0: MetaRouter Trend Short (Baseline)
- **Description:** Existing MetaRouter with trend_short tag only
- **Purpose:** Re-run with corrected measurement tools
- **Baseline metrics (old parser, may be wrong):** 497 trades, PF 1.26, return 31.13%, DD 7.29%
- **Parameters:** Current MetaRouter defaults

### R1: R0 + DMI Directional Separation
- **Hypothesis:** Adding DMI filter (`-DI > +DI`) removes weak short signals
- **Change:** Add single DMI threshold to trend_short conditions
- **Max hyperopt params:** 1 (DMI threshold)

### R2: R1 + EMA Slope / ATR Normalization
- **Hypothesis:** EMA slope normalized by ATR filters out sideways chop
- **Change:** Add slope condition: `(ema20 - ema20.shift(n)) / atr < -threshold`
- **Max hyperopt params:** 2 (lookback n, threshold)

### R3: R1 + Regime Persistence (2-3 candles)
- **Hypothesis:** Require regime to hold for multiple candles reduces flip-flop
- **Change:** Add regime persistence check: `(regime == 'trend_down').rolling(n).min() == 1`
- **Max hyperopt params:** 1 (persistence candles)

### R4: Long Side (CONDITIONAL)
- **Prerequisite:** Only attempt if short-only R0-R3 passes Gate Q
- **Hypothesis:** Long sleeve independent validation with same filters
- **Change:** Enable long signals with mirror conditions
- **Constraint:** Long must independently pass Gate Q recent (2026) PF >= 1.10

**Max candidates:** 5 (R0-R4)  
**Prune rule:** Any candidate failing Gate Q screening (full period OR recent) is dropped immediately

---

## Gate Q Requirements (from Plan)

Candidate ONLY proceeds to expensive validation if ALL criteria met:

### Full Period (2024-01-01 to 2026-08-28)
- Trades >= 450
- PF >= 1.15
- Return > 0
- Expectancy > 0
- Max account DD <= 15%
- Daily Sharpe >= 0.75

### Recent Period (2026-01-01 to 2026-08-28)
- Trades >= 100
- PF >= 1.10
- Return > 0
- Max DD <= 12%

### Walk-Forward OOS (6 folds)
- At least 4/6 folds with return > 0
- No fold with PF < 0.90
- Aggregate OOS: >= 200 trades, PF >= 1.20, DD <= 15%, daily Sharpe >= 1.0

### Side/Pair Robustness
- Each active side: >= 100 trades, PF >= 1.05
- No pair with >= 50 trades and PF < 0.90
- Leave-one-pair-out: aggregate PF stays >= 1.05

### Cost Stress
- 0.4% round-trip cost: PF >= 1.05, DD <= 20%

### Bias/Recursion
- Lookahead analysis: no bias on triggered signals
- Recursive analysis: variance within threshold

### Monte Carlo (Block Bootstrap)
- Probability of ruin < 1%
- Max DD p95 <= 25%
- 10,000 paths, 7-day blocks

---

## Parameter Constraints

- **Max optimized params:** 6 per candidate
- **No optimize:** stop loss, ROI, entry, pair selection simultaneously
- **Prior/range:** Must have economic rationale
- **Forbidden:** Future data, shift(-1), lookahead

---

## Hyperopt Configuration

### Multi-Seed Runs
- **Seeds:** 42, 1337, 20260829
- **Epochs per seed:** 200 (minimum)
- **Selection:** Median validation score across seeds
- **Stability:** Perturb each param ±10%, PF/DD should not collapse

### Spaces
- `buy` space only (short entry conditions)
- Protections enabled in all runs
- Same fee/slippage assumptions as baseline

---

## Validation Pipeline

For candidates passing Gate Q screening:

1. **Lookahead analysis:** All active signals checked, minimum 100 samples per signal type
2. **Recursive analysis:** All indicators used in signals/stops/sizing
3. **Cost stress:** 0.1%, 0.2%, 0.4%, 0.6% round-trip
4. **Pair robustness:** Leave-one-pair-out for all 5 pairs
5. **Walk-forward:** 6 folds, 300 epochs/fold, seed 42
6. **Monte Carlo:** 10k paths, 7-day blocks, seed 42

**Total estimated time:** 3-6 hours per candidate

---

## Acceptance Criteria

### READY FOR DRY-RUN REVIEW
ALL gates must pass:
- Gate R: Measurement tools verified (✓ already passed)
- Gate S: Safety infrastructure complete (✓ already passed)
- Gate Q: Candidate quality validated (pending)
- Gate O: Operational readiness (pending Phase 13)

### RESEARCH ONLY
- Measurement/safety complete
- No candidate passed Gate Q
- Infrastructure ready for future research

### NO ROBUST CANDIDATE
- Multiple candidates screened
- None passed Gate Q
- Temporal decay hypothesis confirmed

---

## Known Limitations

- Data: 5 pairs, 15m timeframe, 2024-01-01 to 2026-08-28
- No 5m data yet (--timeframe-detail validation pending)
- Quarterly breakdown not available in export (only year/month/week/day)
- Exact equity reconstruction limited by overlapping trades

---

## Audit Trail

All runs MUST generate:
- Command with full parameters
- Exit code
- Artifact path with SHA256
- Metrics: trades, PF, return, DD, Sharpe
- Decision: pass/fail with reason
- Timestamp (UTC)

Stored in: `reports/pro_hardening/audit.jsonl`

---

## Failure Modes

### If no candidate passes screening:
- Update PROGRESS.md with verdict: `NO ROBUST CANDIDATE`
- Document why each candidate failed
- Do NOT nosi gates to produce winner
- Infrastructure hardening is still valuable

### If candidate passes screening but fails validation:
- Document exactly which validation step failed
- Do NOT re-tune on holdout
- Candidate is rejected
- May create new candidate with different hypothesis (new experiment ID)

### If candidate passes all validation but fails holdout:
- Experiment fails
- Do NOT adjust splits or re-run
- Document overfitting
- Future experiments need different approach or more data

---

**Locked by:** Claude Sonnet 4  
**Lock time:** 2026-08-29T06:20:00Z  
**Modifications after this point:** FORBIDDEN until experiment complete
