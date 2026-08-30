# Operations Runbook

Safe procedures for common operational tasks. Follow these to avoid data loss, missed trades, or configuration errors.

---

## Prerequisites

Before performing any operation:
1. Know the current bot state (running/stopped, open positions, risk state)
2. Have working backups of config and database
3. Have rollback plan ready
4. Notify team if production

---

## Safe Restart Procedure

**Important:** Freqtrade does NOT hot-reload code or config. You must restart the process for changes to take effect.

### Pre-Restart Checklist

1. **Check open positions:**
   ```bash
   freqtrade show-trades --db-url sqlite:///user_data/tradesv3.dryrun.sqlite
   # Or check via API
   curl http://localhost:8080/api/v1/status
   ```

2. **Backup database:**
   ```bash
   cp user_data/tradesv3.dryrun.sqlite user_data/backups/tradesv3.$(date +%Y%m%d_%H%M%S).sqlite
   ```

3. **Run healthcheck:**
   ```bash
   python tools/healthcheck.py
   ```

4. **Validate config:**
   ```bash
   freqtrade show-config -c user_data/config/config.dryrun.json
   ```

5. **Check risk state:**
   ```bash
   cat user_data/risk_state.json | jq '.'
   # Verify no active halts unless expected
   ```

6. **Note current version:**
   ```bash
   git rev-parse HEAD > /tmp/pre_restart_commit.txt
   ```

### Restart Steps

1. **Stop bot gracefully:**
   ```bash
   # Send SIGTERM (allows graceful shutdown)
   kill -TERM $(pgrep -f "freqtrade trade")
   
   # Wait up to 30 seconds for shutdown
   timeout 30 tail --pid=$(pgrep -f "freqtrade trade") -f /dev/null || kill -KILL $(pgrep -f "freqtrade trade")
   ```

2. **Verify process stopped:**
   ```bash
   pgrep -f "freqtrade trade" && echo "ERROR: Still running" || echo "OK: Stopped"
   ```

3. **Verify database not locked:**
   ```bash
   python -c "import sqlite3; conn = sqlite3.connect('user_data/tradesv3.dryrun.sqlite'); conn.close(); print('OK')"
   ```

4. **Start bot:**
   ```bash
   # Dry-run
   freqtrade trade -c user_data/config/config.dryrun.json --logfile user_data/logs/freqtrade.log &
   
   # Or use systemd/supervisor in production
   systemctl start freqtrade
   ```

5. **Verify startup:**
   ```bash
   # Check process running
   pgrep -f "freqtrade trade"
   
   # Check logs for errors
   tail -50 user_data/logs/freqtrade.log
   
   # Check API responding
   curl http://localhost:8080/api/v1/ping
   ```

6. **Verify strategies loaded:**
   ```bash
   curl http://localhost:8080/api/v1/strategies | jq '.strategies'
   ```

7. **Verify risk state persisted:**
   ```bash
   # If daily/weekly halt was active before restart, verify still active
   cat user_data/risk_state.json | jq '{daily_halt: .daily_halt_active, weekly_halt: .weekly_halt_active}'
   ```

### Post-Restart Validation

Wait 5 minutes, then:

1. **Check no errors in logs:**
   ```bash
   grep -i error user_data/logs/freqtrade.log | tail -20
   ```

2. **Verify data refreshing:**
   ```bash
   python tools/healthcheck.py --check data_freshness
   ```

3. **Verify open positions unchanged:**
   ```bash
   freqtrade show-trades --db-url sqlite:///user_data/tradesv3.dryrun.sqlite
   # Compare count and IDs to pre-restart
   ```

4. **Check guard counters reset:**
   ```bash
   # New process should have zero denials initially
   python tools/healthcheck.py --check guard_denials
   ```

### Rollback

If restart fails or bot behaves incorrectly:

1. **Stop new process:**
   ```bash
   kill -TERM $(pgrep -f "freqtrade trade")
   ```

2. **Restore database backup:**
   ```bash
   cp user_data/backups/tradesv3.TIMESTAMP.sqlite user_data/tradesv3.dryrun.sqlite
   ```

3. **Revert code:**
   ```bash
   git checkout $(cat /tmp/pre_restart_commit.txt)
   ```

4. **Restart with old version:**
   ```bash
   freqtrade trade -c user_data/config/config.dryrun.json --logfile user_data/logs/freqtrade.log &
   ```

5. **Document incident:**
   ```bash
   echo "$(date): Rollback from commit XYZ due to REASON" >> user_data/incident_log.txt
   ```

---

## Emergency Halt

To immediately stop all trading (e.g., exchange hacked, strategy malfunction):

### Option 1: Graceful Halt (Preferred)

1. **Enable forcebuy/forcesell:**
   ```bash
   curl -X POST http://localhost:8080/api/v1/forceexit/all
   ```

2. **Stop bot:**
   ```bash
   kill -TERM $(pgrep -f "freqtrade trade")
   ```

### Option 2: Emergency Kill

If bot not responding:

```bash
kill -KILL $(pgrep -f "freqtrade trade")
```

**Warning:** May leave database in inconsistent state. Check and repair:

```bash
sqlite3 user_data/tradesv3.dryrun.sqlite "PRAGMA integrity_check;"
```

### Option 3: Exchange-Level Halt

If bot cannot be stopped quickly:

1. Revoke API keys at exchange (prevents new orders)
2. Manually close positions via exchange UI
3. Stop bot when safe

---

## Manual Risk State Reset

**When to use:** After reviewing daily/weekly halt, or after fixing circuit breaker root cause.

**Important:** Only reset after thorough review. Halts exist to protect capital.

### Daily Halt Reset

```bash
# Edit risk state file
vi user_data/risk_state.json

# Set daily_halt_active to false and clear realized_pnl_today
# Or wait for UTC midnight (auto-reset)
```

**Alternative:** Delete risk state file (resets everything):
```bash
rm user_data/risk_state.json
# Bot will create fresh state on next startup
```

### Weekly Halt Reset

```bash
# Edit risk state file
vi user_data/risk_state.json

# Set weekly_halt_active to false and clear realized_pnl_week
# No auto-reset - must be manual
```

### Circuit Breaker Reset

```bash
# Edit risk state file
vi user_data/risk_state.json

# Set circuit_breaker.active to false
# Clear circuit_breaker.recent_failures list
```

**After reset:**
```bash
# Restart bot to pick up new state
kill -TERM $(pgrep -f "freqtrade trade")
freqtrade trade -c user_data/config/config.dryrun.json &
```

---

## Config Change Procedure

### Minor Change (Parameters)

Example: Adjust stake amount, add pair to whitelist

1. **Edit config file:**
   ```bash
   vi user_data/config/config.dryrun.json
   ```

2. **Validate syntax:**
   ```bash
   python -m json.tool user_data/config/config.dryrun.json > /dev/null && echo "Valid JSON"
   ```

3. **Validate with Freqtrade:**
   ```bash
   freqtrade show-config -c user_data/config/config.dryrun.json
   ```

4. **Restart bot** (see Safe Restart Procedure above)

### Major Change (Strategy)

Example: Deploy new strategy or change entry logic

1. **Backtest thoroughly:**
   ```bash
   freqtrade backtesting -s NewStrategy --timerange 20240101-20260828
   ```

2. **Run validation suite:**
   ```bash
   freqtrade lookahead-analysis -s NewStrategy
   freqtrade recursive-analysis -s NewStrategy
   ```

3. **Update config to reference new strategy:**
   ```bash
   vi user_data/config/config.dryrun.json
   # Change "strategy": "NewStrategy"
   ```

4. **Force close all open positions** (avoid mixing strategies):
   ```bash
   curl -X POST http://localhost:8080/api/v1/forceexit/all
   ```

5. **Restart with new strategy** (see Safe Restart Procedure)

6. **Monitor closely for 24 hours:**
   - Check logs for errors
   - Verify expected signals generated
   - Run reconciliation after 24h

---

## Database Maintenance

### Backup Schedule

**Recommended:**
- Before every restart: manual backup
- Daily: automated backup (cron)
- Before major changes: manual backup

**Script:**
```bash
#!/bin/bash
BACKUP_DIR="user_data/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup database
cp user_data/tradesv3.dryrun.sqlite $BACKUP_DIR/tradesv3.$TIMESTAMP.sqlite

# Backup config
cp user_data/config/config.dryrun.json $BACKUP_DIR/config.$TIMESTAMP.json

# Backup risk state
cp user_data/risk_state.json $BACKUP_DIR/risk_state.$TIMESTAMP.json 2>/dev/null

# Cleanup old backups (keep 30 days)
find $BACKUP_DIR -name "*.sqlite" -mtime +30 -delete
find $BACKUP_DIR -name "*.json" -mtime +30 -delete

echo "Backup completed: $TIMESTAMP"
```

### Restore from Backup

```bash
# Stop bot first
kill -TERM $(pgrep -f "freqtrade trade")

# Restore database
cp user_data/backups/tradesv3.TIMESTAMP.sqlite user_data/tradesv3.dryrun.sqlite

# Verify integrity
sqlite3 user_data/tradesv3.dryrun.sqlite "PRAGMA integrity_check;"

# Restart bot
freqtrade trade -c user_data/config/config.dryrun.json &
```

### Database Repair

If database corrupted:

```bash
# Stop bot
kill -TERM $(pgrep -f "freqtrade trade")

# Check integrity
sqlite3 user_data/tradesv3.dryrun.sqlite "PRAGMA integrity_check;"

# If corrupted, dump and restore
sqlite3 user_data/tradesv3.dryrun.sqlite .dump > dump.sql
mv user_data/tradesv3.dryrun.sqlite user_data/tradesv3.corrupted.sqlite
sqlite3 user_data/tradesv3.dryrun.sqlite < dump.sql

# Verify
sqlite3 user_data/tradesv3.dryrun.sqlite "PRAGMA integrity_check;"
```

---

## Log Rotation

Freqtrade logs can grow large. Rotate periodically:

### Manual Rotation

```bash
# Move current log
mv user_data/logs/freqtrade.log user_data/logs/freqtrade.$(date +%Y%m%d).log

# Compress old log
gzip user_data/logs/freqtrade.$(date +%Y%m%d).log

# Restart bot (will create new log)
kill -HUP $(pgrep -f "freqtrade trade")
```

### Automated Rotation (logrotate)

```
# /etc/logrotate.d/freqtrade
/path/to/user_data/logs/freqtrade.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0644 user group
    sharedscripts
    postrotate
        kill -HUP $(pgrep -f "freqtrade trade")
    endscript
}
```

---

## Monitoring & Reconciliation

### Daily Routine

1. **Check healthcheck:**
   ```bash
   python tools/healthcheck.py
   ```

2. **Review alerts:**
   - Check Telegram/Slack for overnight alerts
   - Acknowledge and resolve

3. **Check open positions:**
   ```bash
   curl http://localhost:8080/api/v1/status | jq '.open_trades'
   ```

4. **Review yesterday's trades:**
   ```bash
   freqtrade show-trades --db-url sqlite:///user_data/tradesv3.dryrun.sqlite --trade-ids last_24h
   ```

### Weekly Routine

1. **Run reconciliation:**
   ```bash
   python tools/reconcile_dryrun.py \
     --db user_data/tradesv3.dryrun.sqlite \
     --strategy TrendPullback \
     --timerange $(date -d '7 days ago' +%Y%m%d)-$(date +%Y%m%d) \
     --output reports/reconciliation_$(date +%Y%m%d).json
   ```

2. **Review reconciliation report:**
   - Missed signal rate should be < 10%
   - Unexpected trades should be 0%
   - High miss rate → investigate guards

3. **Check performance vs backtest:**
   ```bash
   # Compare dry-run performance to backtest on same period
   # Expect WR within ±15 percentage points
   ```

4. **Review risk state history:**
   - How many times did guards fire?
   - Any halt activations?
   - Document in weekly log

### Monthly Routine

1. **Full backtest with latest data:**
   ```bash
   freqtrade download-data --timerange 20240101-
   freqtrade backtesting -s TrendPullback --timerange 20240101-
   ```

2. **Compare live vs backtest:**
   - Profit factor within 20%?
   - Win rate within 15 percentage points?
   - If divergence large → investigate

3. **Review guard thresholds:**
   - Are guards too tight (high denial rate)?
   - Are guards too loose (poor fills)?
   - Adjust if needed and backtest

4. **Update documentation:**
   - Record any parameter changes
   - Document incidents
   - Update runbook if procedures changed

---

## Incident Response Template

When something goes wrong:

1. **Triage:**
   - What happened? (symptom)
   - When did it start? (timeline)
   - Is trading halted? (current state)
   - Are positions at risk? (exposure)

2. **Stabilize:**
   - Halt trading if needed (emergency halt procedure)
   - Close risky positions manually if needed
   - Prevent further damage

3. **Investigate:**
   - Review logs around incident time
   - Check healthcheck status
   - Check exchange status
   - Review recent code/config changes

4. **Fix:**
   - Apply fix (code, config, or operational)
   - Validate fix in test environment if possible
   - Deploy fix following safe procedures

5. **Verify:**
   - Confirm fix resolved issue
   - Monitor for recurrence
   - Check no side effects

6. **Document:**
   - Root cause
   - Timeline
   - Fix applied
   - Prevention measures
   - Add to incident log

**Incident Log Format:**
```
Date: 2026-08-29
Severity: HIGH
Symptom: Daily halt triggered unexpectedly
Root Cause: Bug in profit calculation after partial exit
Fix: Updated lib/risk_state.py line 87
Prevention: Added test for partial exit case
Downtime: 2 hours (manual review + fix + restart)
```

---

## Common Issues & Solutions

### Issue: Bot Not Placing Trades

**Symptoms:** Running but no trades, even with signals

**Diagnosis:**
```bash
# Check if strategy generating signals
grep -i "enter_long\|enter_short" user_data/logs/freqtrade.log | tail -20

# Check guard denials
python tools/healthcheck.py --check guard_denials

# Check risk state
cat user_data/risk_state.json | jq '.'
```

**Common Causes:**
1. Risk halt active → Review and reset if appropriate
2. Guards denying all entries → Check guard thresholds
3. Max open trades reached → Check config.max_open_trades
4. Insufficient balance → Check available stake

---

### Issue: Trades Not Closing

**Symptoms:** Positions stuck open, not hitting exit conditions

**Diagnosis:**
```bash
# Check open trades
curl http://localhost:8080/api/v1/status

# Check exit signal in logs
grep -i "exit_long\|exit_short" user_data/logs/freqtrade.log | tail -20

# Check stoploss
curl http://localhost:8080/api/v1/status | jq '.open_trades[] | {pair, stop_loss_pct}'
```

**Solutions:**
1. Manual force-exit: `curl -X POST http://localhost:8080/api/v1/forceexit/<trade_id>`
2. Check if stop loss moved incorrectly
3. Check if exchange rejecting exit orders

---

### Issue: Database Locked

**Symptoms:** Cannot restart, errors about database locked

**Diagnosis:**
```bash
# Check for multiple processes
pgrep -fa "freqtrade trade"

# Check database locks
fuser user_data/tradesv3.dryrun.sqlite
```

**Solution:**
```bash
# Kill all freqtrade processes
pkill -9 -f "freqtrade trade"

# Wait 5 seconds
sleep 5

# Verify lock released
fuser user_data/tradesv3.dryrun.sqlite || echo "Released"

# Restart
freqtrade trade -c user_data/config/config.dryrun.json &
```

---

### Issue: High Memory Usage

**Symptoms:** Process consuming excessive RAM

**Diagnosis:**
```bash
# Check process memory
ps aux | grep freqtrade | awk '{print $6/1024 " MB"}'
```

**Common Causes:**
1. Too many pairs (data cached per pair)
2. Large dataframe in strategy
3. Memory leak in custom code

**Solutions:**
1. Reduce pair count
2. Optimize strategy code (don't store large objects)
3. Restart bot daily (workaround for leak)

---

## See Also

- `ALERT_RULES.md` - Alert definitions and responses
- `tools/healthcheck.py` - Automated health checks
- `tools/reconcile_dryrun.py` - Signal/trade reconciliation  
- `HUONG_DAN_SU_DUNG.md` - User guide (Vietnamese)
- `README.md` - Project overview
