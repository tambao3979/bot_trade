# Freqtrade Bot - Live Dry-Run Status
**Date:** 2026-08-29 16:31:00  
**Mode:** Dry-Run (Paper Trading)  
**Strategy:** MetaRouter (Short-only, trend_short setup)

---

## Bot Status: ✅ RUNNING

### Configuration
- **Exchange:** Hyperliquid
- **Trading Mode:** Isolated Futures
- **Timeframe:** 15m
- **Max Open Trades:** 3
- **Stake Currency:** USDC
- **Stake Amount:** Unlimited (risk-based sizing)
- **Initial Balance:** 1000 USDC

### Trading Pairs Monitored
1. BTC/USDC:USDC
2. ETH/USDC:USDC
3. SOL/USDC:USDC ← **Currently has open trade**
4. AVAX/USDC:USDC
5. LINK/USDC:USDC

---

## Current Open Positions

### Trade #5: SOL/USDC:USDC
- **Direction:** LONG (⚠️ Warning: Strategy is configured for SHORT only)
- **Amount:** 2.16 SOL
- **Entry Price:** 104.08 USDC
- **Opened:** 2026-08-29 05:15:15 (11 hours ago)
- **Status:** Active

**Note:** This appears to be a legacy trade from before MetaRouter was configured to short-only mode.

---

## Risk Management Active

### Protection Mechanisms
1. **CooldownPeriod** - 3 candles cooldown after trades
2. **StoplossGuard** - Stops trading after 2 stoplosses within 6 candles
3. **MaxDrawdown** - Halts if drawdown > 10% within 100 candles
4. **LowProfitPairs** - Locks pairs with profit < 0% within 100 candles

### Stop Loss Settings
- **Base Stop Loss:** -2.5%
- **Trailing Stop:** Enabled
- **Trailing Stop Positive:** +1.5%
- **Trailing Stop Offset:** +2.8%
- **Trailing Only Offset Reached:** Yes

### ROI Settings
- **0 minutes:** 7.0% (immediate exit if profit > 7%)
- **45 minutes:** 4.8%
- **120 minutes:** 3.2%
- **300 minutes:** 2.0%

---

## Bot Activity Log

```
16:30:38 - Bot started (PID: 19448, Version: 2026.7)
16:30:40 - Configuration loaded successfully
16:30:53 - Strategy MetaRouter initialized
16:30:53 - Whitelist: 5 pairs configured
16:30:53 - All protections activated
16:30:53 - Found 1 open trade (SOL/USDC:USDC)
16:31:00 - Bot heartbeat - State: RUNNING
16:31:06 - Wallets synced successfully
```

---

## What The Bot Is Doing Now

1. **Monitoring Market Data:**
   - Fetching 15-minute candles for all 5 pairs
   - Calculating technical indicators (EMA, RSI, ADX, Stoch, VWAP)
   - Analyzing market regime (1h timeframe)

2. **Scanning for Signals:**
   - Looking for trend_pullback_short setups
   - Checking entry conditions every 15 minutes
   - Evaluating risk state and protections

3. **Managing Open Position:**
   - Monitoring SOL/USDC:USDC long position
   - Updating trailing stop loss
   - Checking ROI and exit conditions

4. **Safety Checks:**
   - Verifying spread, liquidity, funding rates
   - Checking daily/weekly loss limits
   - Monitoring circuit breaker status

---

## Expected Behavior

### When Bot Finds a Signal
1. Checks all entry conditions are met
2. Verifies no protections are active
3. Confirms execution guards pass
4. Places limit order at target price
5. Monitors position with trailing stop

### Current Market Regime
Bot is waiting for **trend_down** conditions to enter SHORT positions:
- Price below EMA200
- EMA20 below EMA50
- ADX > 20 (strong trend)
- Stochastic bearish crossover
- Volume above 80% of MA

---

## Performance Expectations

Based on backtest results:
- **Historical Win Rate:** 61.7% (308W / 191L)
- **Recent Win Rate:** 33.3% (Aug 2026) ⚠️ **DEGRADED**
- **Profit Factor:** 1.36 (overall)
- **Average Trade Duration:** 11h 26m
- **Max Drawdown:** 6.94%

**⚠️ WARNING:** Strategy showing temporal decay - recent performance significantly worse than historical.

---

## How to Monitor the Bot

### Real-Time Monitoring
```bash
# Watch bot logs
tail -f user_data/logs/freqtrade.log

# Check bot status
freqtrade status -c user_data/config/config.base.json -c user_data/config/config.dryrun.json

# View open trades
freqtrade show_trades -c user_data/config/config.base.json -c user_data/config/config.dryrun.json
```

### Health Check
```bash
python tools/healthcheck.py
```

### Reconciliation (After 24h)
```bash
python tools/reconcile_dryrun.py \
  --db tradesv3.dryrun.sqlite \
  --strategy MetaRouter \
  --timerange 20260829-20260830
```

---

## Next Steps

### Immediate Actions
1. ✅ Bot is running successfully
2. ⏳ Wait for market conditions to generate signals
3. 📊 Monitor for 24-48 hours
4. 🔍 Run reconciliation to verify signals vs. trades

### If You Want to Stop the Bot
```bash
# Find and kill the process
ps aux | grep freqtrade
kill <PID>

# Or use Ctrl+C if running in foreground
```

### If You Want to See Trades Happen Faster
- The bot checks every 15 minutes for new candles
- With current win rate degradation (33.3%), expect few profitable signals
- Consider testing with different market conditions or enabling long trades

---

## Important Reminders

🔴 **DO NOT SWITCH TO LIVE TRADING**
- Current win rate: 33.3% (failing)
- Temporal decay detected
- Strategy not validated for deployment
- Need 30-day successful dry-run first

✅ **Safe to Continue Dry-Run**
- No real money at risk
- Good for observing behavior
- Collecting data for analysis
- Testing infrastructure

---

**Bot Status:** Running normally, waiting for valid signals  
**Risk Level:** Zero (paper trading only)  
**Recommendation:** Let run for 24-48 hours, then analyze results
