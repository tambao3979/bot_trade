# Freqtrade Trading Bot

Crypto futures trading bot built on Freqtrade with hardened measurement and safety infrastructure.

**Status:** Research only - no deployment-ready candidate validated  
**Last Updated:** 2026-08-29  
**Test Coverage:** 138 tests, 100% pass

## Quick Start

### Prerequisites
- Python 3.12+ (tested with 3.12.8)
- Freqtrade 2026.7
- Windows/Linux/macOS

### Installation

1. **Clone and setup environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings (API keys, etc.)
   ```

3. **Download historical data:**
   ```bash
   freqtrade download-data \
     --exchange binance \
     --pairs BTC/USDT:USDT ETH/USDT:USDT SOL/USDT:USDT BNB/USDT:USDT XRP/USDT:USDT \
     --timeframes 15m 1h \
     --timerange 20240101- \
     --trading-mode futures
   ```

4. **Run tests:**
   ```bash
   pytest tests/ -v
   ```

5. **Validate configuration:**
   ```bash
   freqtrade show-config -c user_data/config/config.base.json -c user_data/config/config.backtest.json
   ```

### Running Backtests

```bash
# Single strategy backtest
freqtrade backtesting \
  -c user_data/config/config.base.json \
  -c user_data/config/config.backtest.json \
  -s TrendPullback \
  --timerange 20240101-20260828

# With temporal breakdown
python tools/report.py user_data/backtest_results/backtest-result-*.json --output reports/backtest_report.md
```

### Dry-Run (Paper Trading)

**Important:** Before running dry-run, read `docs/RUNBOOK.md` for safe operational procedures.

```bash
# Start dry-run
freqtrade trade \
  -c user_data/config/config.base.json \
  -c user_data/config/config.dryrun.json \
  --logfile user_data/logs/freqtrade.log

# Health check (in another terminal)
python tools/healthcheck.py

# Reconciliation (after 24h)
python tools/reconcile_dryrun.py \
  --db user_data/tradesv3.dryrun.sqlite \
  --strategy TrendPullback \
  --timerange 20260828-20260829
```

## Project Structure

```
.
├── user_data/
│   ├── config/           # Configuration files
│   │   ├── config.base.json      # Base config (shared)
│   │   ├── config.backtest.json  # Backtest overlay
│   │   └── config.dryrun.json    # Dry-run overlay
│   ├── strategies/       # Trading strategies
│   │   ├── base/
│   │   │   └── BaseRiskStrategy.py  # Risk management base
│   │   ├── TrendPullback.py
│   │   ├── MetaRouter.py
│   │   └── lib/          # Strategy library
│   │       ├── indicators.py
│   │       ├── regime.py
│   │       ├── structure.py
│   │       ├── guards.py
│   │       ├── snapshot.py    # Market snapshot cache
│   │       └── risk_state.py  # Persistent risk state
│   └── data/             # Market data (gitignored)
├── tools/
│   ├── report.py         # Backtest report generator
│   ├── walkforward.py    # Walk-forward validation
│   ├── montecarlo.py     # Monte Carlo simulation
│   ├── healthcheck.py    # Operational health checks
│   └── reconcile_dryrun.py  # Signal/trade reconciliation
├── tests/                # 138 tests
├── reports/              # Generated reports
├── docs/
│   ├── RUNBOOK.md        # Operational procedures
│   └── ALERT_RULES.md    # Alert specifications
├── DECISIONS.md          # Architecture decisions
├── NEXT_STEPS.md         # Development roadmap
└── README.md             # This file
```

## Available Strategies

| Strategy | Type | Status | Notes |
|----------|------|--------|-------|
| **TrendPullback** | Trend following | ⚠ Research | Temporal decay detected (2026 PF < 1.0) |
| **MetaRouter** | Meta/ensemble | ⚠ Research | Short-only passes screening |
| **LiquiditySweep** | Liquidity grab | 🚧 Planned | Not implemented |
| **RangeReversion** | Mean reversion | 🚧 Planned | Not implemented |

**No strategy is currently validated for deployment.** See `reports/pro_hardening/FINAL.md` for details.

## Tools

### Report Generator
```bash
python tools/report.py <backtest-result.zip> --output report.md
```

### Walk-Forward Validation
```bash
python tools/walkforward.py \
  --strategy TrendPullback \
  --timerange 20240101-20260828 \
  --folds 6 \
  --train-days 365 \
  --test-days 90
```

### Monte Carlo Simulation
```bash
python tools/montecarlo.py \
  --input daily_profit.json \
  --paths 10000 \
  --block-size 7 \
  --seed 42
```

### Health Check
```bash
python tools/healthcheck.py
# Returns exit code 0 if healthy, non-zero with issues
```

### Reconciliation
```bash
python tools/reconcile_dryrun.py \
  --db user_data/tradesv3.dryrun.sqlite \
  --strategy TrendPullback \
  --timerange 20260820-20260829
```

## Configuration

Config composition: `base.json` + overlay (`backtest.json` or `dryrun.json`)

Environment variables override config (FREQTRADE__SECTION__KEY format):
```bash
export FREQTRADE__EXCHANGE__KEY="your_api_key"
export FREQTRADE__EXCHANGE__SECRET="your_api_secret"
```

See `.env.example` for full list.

## Safety Features

- **Persistent risk state:** Daily/weekly loss limits survive restarts
- **Execution guards:** Fail-closed checks for spread, liquidity, funding
- **Snapshot cache:** No network I/O in trading callbacks
- **Circuit breaker:** Halts after repeated failures
- **Position sizing:** Fixed fractional risk with maximum caps
- **Protections:** Cooldown, StoplossGuard, MaxDrawdown, LowProfitPairs

## Testing

```bash
# All tests
pytest tests/ -v

# Specific suite
pytest tests/test_risk_state.py -v

# With coverage
pytest --cov=user_data/strategies --cov=tools --cov-report=html
```

**Current:** 138 tests, 100% pass (1 skip)

## Documentation

- **[DECISIONS.md](DECISIONS.md)** - Technical decisions and corrections
- **[NEXT_STEPS.md](NEXT_STEPS.md)** - Development priorities
- **[docs/RUNBOOK.md](docs/RUNBOOK.md)** - Operational procedures
- **[docs/ALERT_RULES.md](docs/ALERT_RULES.md)** - Alert specifications
- **[reports/pro_hardening/FINAL.md](reports/pro_hardening/FINAL.md)** - Hardening report
- **[HUONG_DAN_SU_DUNG.md](HUONG_DAN_SU_DUNG.md)** - User guide (Vietnamese)

## Current Status

**Phase completed:** Measurement & safety infrastructure hardening (Phases 0-8)  
**Verdict:** `RESEARCH ONLY - NO ROBUST CANDIDATE`

### What Works
- ✅ Accurate measurement tools (parser, walk-forward, Monte Carlo)
- ✅ Persistent risk state (survives restarts, fails closed)
- ✅ Execution guards (no network I/O in callbacks)
- ✅ 138 passing tests (+65 from baseline)
- ✅ Healthcheck and reconciliation tools

### What Doesn't
- ❌ No viable trading candidate (temporal decay, recent PF failures)
- ❌ Baseline TrendPullback fails Gate Q (2026 PF 0.81 < 1.0)
- ❌ Short-only candidates fail recent performance requirements
- ⚠️ No CI pipeline yet
- ⚠️ Alert infrastructure not implemented

### Next Steps

**If continuing research:**
1. Remove BTC pair (consistently losing)
2. Research new regime-adaptive strategies
3. Add more pairs for diversification
4. Wait for favorable market regime

**Before any deployment:**
1. Complete Gate Q validation on new candidate
2. 30-day dry-run soak with reconciliation
3. Implement alert infrastructure
4. Complete operational tooling (see NEXT_STEPS.md)

## License

MIT (see LICENSE file)

## Contributing

This is a personal research project. PRs accepted for:
- Bug fixes in measurement tools
- Additional test coverage
- Documentation improvements

Not accepting PRs for:
- New strategies (research is personal)
- Relaxing safety gates
- Removing validation steps

## Disclaimer

**This software is for research and educational purposes only.**

- Trading cryptocurrencies carries significant risk of loss
- Past performance does not guarantee future results
- No strategy in this repository has been validated for live deployment
- Use at your own risk with capital you can afford to lose
- Always start with dry-run and validate thoroughly
- The authors are not liable for any trading losses

**DO NOT deploy strategies showing temporal decay or failing Gate Q validation.**
