# Alert Rules Specification

This document defines alert rules for production bot monitoring. These rules should be implemented in your alerting infrastructure (Telegram, Slack, PagerDuty, etc.).

**Important:** This is a specification. Actual implementation requires:
1. Alert transport (Telegram bot, Slack webhook, etc.)
2. Rate limiting and deduplication
3. Severity classification
4. On-call rotation integration

---

## Alert Severity Levels

| Level | Response Time | Examples |
|-------|---------------|----------|
| **CRITICAL** | Immediate (page on-call) | Process down, exchange unavailable, circuit breaker |
| **HIGH** | < 15 minutes | Daily loss halt, stale data, repeated errors |
| **MEDIUM** | < 1 hour | Guard denials, config drift, low disk |
| **LOW** | Next business day | High guard denial rate, slow API |

---

## Process Health Alerts

### CRITICAL: Bot Process Down
**Trigger:** Freqtrade process not running (detected by healthcheck)  
**Action:** Page on-call immediately  
**Rationale:** Open positions are not being managed

**Check:**
```bash
# Via healthcheck
python tools/healthcheck.py --check process

# Or directly
pgrep -f "freqtrade trade" || echo "ALERT: Process down"
```

**Recovery:**
1. Check logs for crash reason
2. Verify database not corrupted
3. Verify config file valid
4. Restart following runbook (see RUNBOOK.md)

---

### HIGH: Process Stale (Old Code Running)
**Trigger:** Process code hash != current source hash (detected by healthcheck)  
**Action:** Alert within 15 minutes  
**Rationale:** Code changes not active, potential behavior mismatch

**Check:**
```bash
python tools/healthcheck.py --check code_hash
```

**Recovery:**
1. Review what changes are not live
2. Schedule safe restart window
3. Follow restart runbook

---

## Data Freshness Alerts

### CRITICAL: Exchange Unavailable
**Trigger:** Cannot fetch data from exchange for > 5 minutes  
**Action:** Page immediately  
**Rationale:** Cannot trade, positions at risk

**Check:**
- Monitor exchange API errors in logs
- Healthcheck detects last successful data fetch

**Recovery:**
1. Check exchange status page
2. If exchange down: wait for recovery
3. If network/credentials issue: fix immediately
4. Consider emergency halt if prolonged

---

### HIGH: Stale Market Data
**Trigger:** Latest candle > 2 timeframes old  
**Action:** Alert within 15 minutes  
**Rationale:** Trading on outdated data, risk of bad fills

**Example:** With 15m timeframe, alert if no candle received in 30+ minutes

**Check:**
```bash
python tools/healthcheck.py --check data_freshness
```

**Recovery:**
1. Check exchange connectivity
2. Check API rate limits
3. Review Freqtrade logs for errors
4. Restart data refresh if needed

---

### HIGH: Stale Market Snapshot
**Trigger:** Cached orderbook/ticker > TTL (default 60s)  
**Action:** Alert if persists > 5 minutes  
**Rationale:** Guards will fail-closed, blocking all entries

**Check:**
```bash
# Logs will show "snapshot stale" denial reasons
grep -c "snapshot_stale" logs/freqtrade.log
```

**Recovery:**
1. Check collector function running
2. Check exchange API connectivity
3. Review rate limit status

---

## Risk State Alerts

### CRITICAL: Daily Loss Halt Triggered
**Trigger:** Realized daily loss exceeds threshold (default 2%)  
**Action:** Page immediately  
**Rationale:** Risk limit breached, trading halted until manual review

**Check:**
```bash
python tools/healthcheck.py --check risk_state
# Or check risk state file
cat user_data/risk_state.json | jq .daily_halt_active
```

**Recovery:**
1. Review trades that caused loss
2. Analyze if losses are within expected variance or indicate issue
3. Manually reset halt only after thorough review
4. Document decision in incident log

**Manual Reset:**
```python
# Edit user_data/risk_state.json
# Set "daily_halt_active": false
# Or delete file to reset (UTC midnight auto-reset also works)
```

---

### CRITICAL: Weekly Loss Halt Triggered  
**Trigger:** Realized weekly loss exceeds threshold (default 5%)  
**Action:** Page immediately  
**Rationale:** Severe risk limit breached, extended halt

**Recovery:**
1. Review full week of trades
2. Statistical analysis: bad luck vs strategy failure
3. Consider strategy adjustment or parameter change
4. Manual reset required (no auto-reset)

---

### CRITICAL: Circuit Breaker Triggered
**Trigger:** 3+ trade failures in rolling window  
**Action:** Page immediately  
**Rationale:** System malfunction, could be exchange issue or code bug

**Check:**
```bash
# Check circuit breaker state
cat user_data/risk_state.json | jq .circuit_breaker
```

**Recovery:**
1. Review failed trade reasons in logs
2. Check exchange status
3. Verify sufficient balance
4. Check for exchange API changes
5. Manual reset after root cause fixed

---

### HIGH: Max Drawdown Protection Active
**Trigger:** Freqtrade protection plugin activated  
**Action:** Alert within 15 minutes  
**Rationale:** Strategy hitting max drawdown, trading paused

**Check:**
```bash
# Freqtrade logs will show protection activation
grep "activated" logs/freqtrade.log | grep -i protection
```

**Recovery:**
1. Review recent trades and market conditions
2. Assess if drawdown is statistical variance or strategy breakdown
3. Wait for protection cooldown or manually unlock
4. Consider strategy adjustment if frequent activation

---

## Execution Quality Alerts

### MEDIUM: High Guard Denial Rate
**Trigger:** > 30% of signals denied by guards in 1 hour window  
**Action:** Review within 1 hour  
**Rationale:** May indicate market condition change or misconfiguration

**Check:**
```bash
# Denial counters from healthcheck
python tools/healthcheck.py --check guard_denials --threshold 0.30
```

**Common Causes:**
- Spread too wide (low liquidity period)
- Funding rate extreme (futures markets)
- Snapshot stale (data collection issue)
- Volume below threshold (quiet market)

**Action:**
- Review guard logs for denial reasons
- Assess if conditions are temporary (no action) or indicate issue
- Adjust thresholds if consistently denying valid opportunities

---

### MEDIUM: Repeated Guard Denials (Same Reason)
**Trigger:** Same guard denial reason > 10 times in 1 hour  
**Action:** Review within 1 hour  
**Rationale:** Systematic issue preventing entries

**Example:** If "spread_too_wide" fires 10+ times, spread threshold may be too tight

**Recovery:**
1. Identify which guard is blocking
2. Check if market conditions justify (e.g., holiday low liquidity)
3. Adjust threshold if misconfigured
4. Document if normal for current regime

---

### LOW: Slow Callback Execution
**Trigger:** confirm_trade_entry p99 latency > 100ms  
**Action:** Monitor, investigate if persists > 1 day  
**Rationale:** Risk of missed fills, but not immediate danger

**Check:**
```bash
# Benchmark callback latency
# (Requires instrumentation in strategy code)
grep "callback_latency_ms" logs/freqtrade.log | tail -100
```

**Recovery:**
1. Check if network calls in callback (should be none)
2. Profile callback code for bottlenecks
3. Optimize if needed

---

## Database & Storage Alerts

### HIGH: Database Lock Detected
**Trigger:** SQLite database locked for > 60 seconds  
**Action:** Alert within 15 minutes  
**Rationale:** Trading may hang, risk state updates blocked

**Check:**
```bash
python tools/healthcheck.py --check database
```

**Recovery:**
1. Check for stale process holding lock
2. Verify no backup running
3. Check disk I/O performance
4. Restart if deadlocked

---

### MEDIUM: Low Disk Space
**Trigger:** Available disk < 10% or < 1GB  
**Action:** Alert within 1 hour  
**Rationale:** Database/logs may stop writing

**Check:**
```bash
python tools/healthcheck.py --check disk_space
```

**Recovery:**
1. Archive old logs
2. Clean up old backtest artifacts
3. Rotate log files
4. Add disk space if needed

---

### LOW: Large Log File
**Trigger:** Log file > 500MB  
**Action:** Next business day  
**Rationale:** May slow log parsing, but not urgent

**Recovery:**
- Enable log rotation
- Archive old logs
- Compress historical logs

---

## Configuration Alerts

### CRITICAL: Config File Missing/Invalid
**Trigger:** Config file cannot be loaded (detected at startup or healthcheck)  
**Action:** Page immediately  
**Rationale:** Cannot start/restart bot

**Check:**
```bash
freqtrade show-config -c user_data/config/config.live.json
```

**Recovery:**
1. Restore from backup
2. Validate JSON syntax
3. Check file permissions
4. Verify environment variables

---

### HIGH: Secret/API Key Missing
**Trigger:** Required environment variable not set  
**Action:** Alert within 15 minutes  
**Rationale:** Bot cannot authenticate to exchange

**Check:**
```bash
python tools/healthcheck.py --check secrets
```

**Recovery:**
1. Set missing environment variables
2. Check .env file loaded
3. Restart process to pick up new env

---

### MEDIUM: Config Drift Detected
**Trigger:** Live config differs from version-controlled config  
**Action:** Review within 1 hour  
**Rationale:** May indicate manual change not committed

**Check:**
```bash
# Compare running config to file
diff <(freqtrade show-config) user_data/config/config.live.json
```

**Recovery:**
1. If intentional: commit to version control
2. If accidental: revert to known good config
3. Restart with correct config

---

## Reconciliation Alerts

### MEDIUM: Signal/Trade Mismatch
**Trigger:** Reconciliation shows > 20% missed signals in 24h  
**Action:** Review within 1 hour  
**Rationale:** Strategy not executing as expected

**Check:**
```bash
python tools/reconcile_dryrun.py \
  --db user_data/tradesv3.dryrun.sqlite \
  --strategy TrendPullback \
  --timerange 20260828-20260829
```

**Recovery:**
1. Review missed signal reasons
2. Check guard denial logs
3. Verify position limits not exhausted
4. Check if signals valid but blocked by risk state

---

### MEDIUM: Unexpected Trades
**Trigger:** Reconciliation shows trades without matching signals  
**Action:** Review within 1 hour  
**Rationale:** May indicate code bug or race condition

**Check:**
- Reconciliation report "unexpected" status

**Recovery:**
1. Review unexpected trade timestamps
2. Check if signal generated but not logged
3. Investigate duplicate signal handling
4. Check for manual trades (if enabled)

---

## Alert Implementation Notes

### Rate Limiting
- Group similar alerts (e.g., "10 spread denials" not "spread denial" × 10)
- Suppress repeat alerts for same issue within 1 hour
- Send summary digest for LOW severity (daily)

### Deduplication
- Hash alert fingerprint: (rule_name, context, severity)
- Only alert if fingerprint changed or last alert > threshold

### Severity Escalation
- MEDIUM → HIGH if unresolved for 4 hours
- HIGH → CRITICAL if unresolved for 12 hours

### On-Call Rotation
- CRITICAL: page current on-call
- HIGH: notify on-call + escalate if no ack in 30 min
- MEDIUM/LOW: post to team channel

### Example Implementation (Pseudocode)
```python
def send_alert(rule, severity, context):
    fingerprint = hash((rule, context, severity))
    
    if recently_alerted(fingerprint, window="1h"):
        return  # Suppress duplicate
    
    if severity == "CRITICAL":
        page_oncall(rule, context)
    elif severity == "HIGH":
        notify_oncall(rule, context)
        schedule_escalation(fingerprint, delay="30m")
    elif severity == "MEDIUM":
        post_to_channel(rule, context)
    else:  # LOW
        add_to_daily_digest(rule, context)
    
    record_alert(fingerprint, timestamp=now())
```

---

## Testing Alerts

Before going live, test each alert:

1. **Process down:** Stop bot, verify page sent
2. **Data stale:** Block exchange API, verify alert
3. **Daily halt:** Manually trigger in test env
4. **Guard denials:** Force denial conditions
5. **Disk space:** Create large test file
6. **Config invalid:** Corrupt config, verify detection

**Test Checklist:**
- [ ] Alerts delivered to correct destinations
- [ ] Severity routing works (page vs notify vs digest)
- [ ] Rate limiting prevents spam
- [ ] Deduplication prevents duplicates
- [ ] Escalation works for unacked alerts
- [ ] Recovery notifications sent when resolved

---

## Alert Log

Maintain a log of alerts for incident review:

```
timestamp,rule,severity,context,acked_by,resolved_at,resolution_notes
2026-08-29T12:34:56Z,daily_halt,CRITICAL,loss_2.1pct,alice,2026-08-29T13:00:00Z,reviewed_trades_variance
```

This enables:
- Alert frequency analysis
- Mean time to acknowledge (MTTA)
- Mean time to resolution (MTTR)
- Alert tuning (reduce false positives)

---

## See Also

- `RUNBOOK.md` - Safe restart and recovery procedures
- `tools/healthcheck.py` - Automated health checks
- `tools/reconcile_dryrun.py` - Signal/trade reconciliation
- `user_data/risk_state.json` - Current risk state
