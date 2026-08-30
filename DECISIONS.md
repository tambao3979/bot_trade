# Decisions

- **Exchange**: Hyperliquid (Perp DEX) – default per the plan’s “Phương án A”.
- **Stake currency**: USDC (native on Hyperliquid).
- **Data fallback**: if Hyperliquid historical data is insufficient, Binance will be used for research, with divergence warnings recorded here.
- **Trading mode**: futures / perpetuals, isolated margin, max leverage 2x.

---

## Entry Frequency Increase Research (2026-08-29)

**Objective**: Increase TrendPullback entry frequency from 989 trades (1.04/day) to ≥1,187 trades (1.25/day) while maintaining Gate A risk thresholds.

**Gate A Requirements**: Total trades ≥1,187, trades/day ≥1.25, PF ≥1.05, return >0, max DD ≤25%, Sharpe ≥0.45, both long/short ≥15% each, all tags PF ≥1.00, no relaxed risk parameters.

**Tested Approaches**:
1. **Candidate A** (Recent Short Cross Lookback): Relaxed stochastic cross timing to 2-candle window
   - Result: 1,057 trades, PF 1.03, DD 27.88% → **REJECTED** (multiple gate violations)
   
2. **Candidate B** (Recent Short Pullback Touch): Relaxed EMA20 touch timing to 2-candle window
   - Result: 1,013 trades, PF 1.03, DD 26.45% → **REJECTED** (multiple gate violations)

3. **MetaRouter Integration**: Enabled only profitable trend_short setup (baseline PF 1.71)
   - Result: 497 trades (short only), no long exposure → **REJECTED** (insufficient trades, no diversification)

**Root Cause**: Temporal constraint relaxation allowed late entries with degraded quality. Profit factor dropped from 1.71 → 1.08-1.09 for short trades; drawdown increased beyond 25% threshold.

**Final Decision**: **NO SAFE FREQUENCY INCREASE FOUND**

**Winner**: TrendPullback Phase 3 Baseline (unchanged)
- Total Trades: 989 (492 long / 497 short)
- Trades/Day: 1.04
- Profit Factor: 1.0524 (long: 0.8756, short: 1.2568)
- Total Return: +14.02% (long: -17.84%, short: +31.86%)
- Max Drawdown: 23.86%
- Sharpe Ratio: 0.48
- Classification: **RESEARCH ONLY** (Gate B not evaluated)

**⚠ Temporal Decay Blocker**: Clear performance degradation over time:
- 2024: PF 1.29 (393 trades)
- 2025: PF 1.03 (377 trades)
- 2026: PF 0.81 (219 trades) ← **LOSING YEAR**

**⚠ Long Side Failure**: Long side has been losing overall (-17.84% return, PF 0.88 < 1.0). Combined profitability comes entirely from short side.

**Conclusion**: Baseline 989 trades does NOT represent stable exploitable edge. Temporal decay and long-side failure indicate regime shift or overfitting. Strategy requires fundamental redesign, not frequency tuning. All frequency increase attempts violated multiple Gate A requirements.

**Artifacts**: See `reports/entry_frequency/FINAL.md` for complete analysis.

**Next Action**: None - No candidate passed Gate A. No dry-run authorization. Strategy requires OOS validation (Gate B) before deployment consideration.

---

## Pro Hardening Corrections (2026-08-29, Phase 2)

**Source**: `reports/pro_hardening/ERRATA.md`

All numbers above have been re-verified using corrected report parser (tools/report.py) against original ZIP archives with SHA256 provenance tracking. Previous reports may have used incorrect field names or unit interpretations.

**Key Corrections**:
1. Confirmed long/short breakdown uses `trade_count_long`/`trade_count_short` (not `trades_long`/`trades_short`)
2. Confirmed profit_total is a ratio (0.1402) not percent (14.02 is derived)
3. Confirmed max_drawdown_account (ratio) is correct field for account DD percentage
4. Added temporal decay evidence from periodic_breakdown (year-level data available)
5. Clarified that MetaRouter short-only (497 trades, PF 1.25) is a DIFFERENT strategy configuration, not comparable to TrendPullback baseline which includes both directions

**Regression Tests**: All baseline numbers verified within tolerance 1e-8 (ratio) and 1e-4 (percent) in `tests/test_report_parser.py` and `tests/test_temporal_decay.py`.

