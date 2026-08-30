# Hướng dẫn vận hành bot Freqtrade

Tài liệu này phản ánh trạng thái sau đợt hardening hạ tầng đo lường và an toàn ngày 29-08-2026. Bot đã được kiểm tra trên Freqtrade 2026.7 và Python 3.12.8. Kết quả kiểm thử hiện tại là **138 test PASS** (+75 tests so với baseline).

> Đây là phần mềm giao dịch có rủi ro cao, không phải cam kết lợi nhuận. Không chuyển sang live chỉ vì backtest, lookahead hoặc test đơn vị đã pass.

## ⚠️ QUAN TRỌNG: Trạng thái hiện tại

**Ngày**: 2026-08-29  
**Kết luận**: **RESEARCH ONLY - NO ROBUST CANDIDATE**

Sau khi sửa lỗi schema parser và kiểm tra lại tất cả số liệu, phát hiện:
- **TrendPullback Baseline** có temporal decay nghiêm trọng: 2024 PF 1.29 → 2025 PF 1.03 → 2026 PF 0.81 (thua)
- **Long side** thua tổng thể: -17.84% return, PF 0.88
- **Short side** cũng suy giảm: 2024 PF 1.72 → 2026 PF 1.08
- **Các candidate R0, R1** không qua Gate Q (recent period PF < 1.10 hoặc trade count thấp)

**Trạng thái**: Chưa có strategy nào được validate để deploy  
**Chi tiết**: Xem `reports/pro_hardening/FINAL.md`

## ✅ Đã hoàn thành trong đợt hardening

1. **Đo lường chính xác**: Parser backtest mới đọc đúng schema Freqtrade 2026.7
2. **Walk-forward cải tiến**: Daily equity reconstruction, temporal splits với embargo
3. **Monte Carlo block bootstrap**: Bảo toàn cấu trúc regime thay vì IID
4. **Persistent risk state**: Daily/weekly halt survives restarts, fail-closed
5. **Execution guards**: Snapshot cache, không network I/O trong callbacks
6. **Công cụ vận hành**: Healthcheck, reconciliation, runbook, alert specs

---

## 1. Kiến trúc và các thành phần

```text
user_data/
  config/
    config.base.json                 Cấu hình Hyperliquid futures dùng vận hành
    config.dryrun.json               Ghi đè an toàn cho dry-run, Telegram tắt mặc định
    config.validation.binance.json   Cấu hình Binance futures chỉ phục vụ kiểm thử dữ liệu
  strategies/
    base/BaseRiskStrategy.py         Risk engine dùng chung
    lib/indicators.py                Chỉ báo an toàn số học, không lookahead
    lib/regime.py                    Phân loại trend/range/chaos
    lib/structure.py                 Swing, FVG, liquidity structure chỉ dùng nến đã có
    lib/guards.py                    Spread, slippage, thanh khoản, funding, daily-loss guard
    TrendPullback.py                 Giao dịch pullback trong xu hướng
    RangeReversion.py                Mean reversion khi thị trường range
    LiquiditySweep.py                Reversal sau sweep thanh khoản
    MetaRouter.py                    Router tổng hợp theo market regime
tools/
  walkforward.py                     Hyperopt + OOS rolling validation
  montecarlo.py                      Bootstrap Monte Carlo cho OOS trades
tests/                               Regression tests cho risk, strategy và tools
reports/                             Kết quả validation và smoke test
```

`BaseRiskStrategy` là lớp cha của bốn chiến lược. Nó thực hiện các việc sau:

- Chỉ xử lý candle mới; ATR dùng candle áp chót, không dùng candle có thể đang mở.
- Size theo Fixed Fractional Risk: `risk_capital = equity x 0.5%`; notional mục tiêu là `risk_capital / (ATR / giá)`; collateral được chia cho leverage. Notional bị chặn ở 25% equity, leverage tối đa 2x và lệnh dưới ngưỡng tối thiểu bị từ chối, không bị nâng size để ép khớp.
- Circuit breaker kép: dừng entry ở lỗ ngày 2% hoặc drawdown đỉnh 10%. Freqtrade protections bổ sung cooldown, stoploss guard, max drawdown và low-profit pairs.
- Trước entry live/dry-run phải vượt spread <= 15 bps, đủ độ sâu order book với slippage <= 30 bps, volume 24h >= 1 triệu, funding tuyệt đối <= 0.05%. Thiếu dữ liệu là từ chối lệnh.
- Stoploss tùy biến được bật: hòa vốn sau +1R, trail ATR sau +1.5R; có một lần chốt 50% sau +1R.

`MetaRouter` gán rõ tag và chỉ chọn tín hiệu theo regime 1h đã đóng:

| Regime | Nhánh được ưu tiên |
|---|---|
| `trend_up` / `trend_down` | `TrendPullback` theo chiều xu hướng |
| `range` | `RangeReversion` |
| `chaos` | Không chủ động vào theo router; tránh nhiễu |
| Tất cả regime hợp lệ | `LiquiditySweep` chỉ là fallback, không ghi đè tín hiệu có sẵn |

Regime 1h được dịch thêm một giờ rồi `merge_asof` lùi, nên một candle 15m chỉ nhìn thấy candle 1h đã đóng. `VWAP` được reset theo ngày UTC; điều này tránh chênh lệch phụ thuộc độ dài warm-up trong backtest.

## 2. Các lỗi đã vá và nâng cấp (2026-08-29)

### Đo lường và validation
| Phát hiện | Khắc phục |
|---|---|
| Parser đọc sai schema Freqtrade 2026.7 | Viết lại `tools/report.py`: đúng field names (`trade_count_long/short`, `max_drawdown_account`), đúng units (ratio vs percent) |
| Temporal decay không được kiểm tra tự động | Thêm `tests/test_temporal_decay.py` với 4 tests verify PF theo năm |
| Walk-forward compound trade ratios sai | Viết lại `tools/walkforward.py`: daily equity từ cash-flow, không compound `profit_ratio` |
| Monte Carlo IID phá hủy regime clustering | Viết lại `tools/montecarlo.py`: moving-block bootstrap (default 7 days) |
| Không có provenance tracking | Tất cả reports ghi source file SHA256, strategy, timerange, generated_at |

### An toàn vận hành
| Phát hiện | Khắc phục |
|---|---|
| Network I/O trong callbacks (possible) | Tạo `lib/snapshot.py`: MarketSnapshot cache với TTL, collector/evaluator separation |
| Risk state mất khi restart | Tạo `lib/risk_state.py`: atomic writes, daily/weekly PnL persistent, fail-closed on corruption |
| Funding check fail-open | Sửa `lib/guards.py`: funding unknown → deny entry, không assume safe |
| Stop mechanism không rõ ràng | Clarify: trailing stop active, `use_custom_stoploss=False`, custom stop disabled |
| Protections thiếu trade_limit | Thêm `trade_limit` explicit cho StoplossGuard, LowProfitPairs |

### Cấu hình và secrets
| Phát hiện | Khắc phục |
|---|---|
| `.env.example` sai naming convention | Sửa sang `FREQTRADE__SECTION__KEY` format |
| `.gitignore` thiếu DB/logs | Thêm `*.sqlite*`, `*.log*`, `user_data/risk_state.json` |
| Config dryrun-only lỗi | Document compose pattern: base + overlay, không dùng dryrun-only |
| Không có lockfile | Thêm instruction dùng `uv` lockfile (requirements.txt là input) |

### Legacy fixes (từ vòng trước)
| Phát hiện | Khắc phục |
|---|---|
| Dùng cấu trúc swing/FVG có khả năng cần nến tương lai | Viết lại bằng `shift` quá khứ, không có `shift(-n)` |
| VWAP tích lũy xuyên toàn bộ lịch sử làm recursive variance | Reset VWAP theo phiên ngày UTC |
| Chia cho 0, `NaN`, `Inf` trong indicators/risk | Chuẩn hóa finite, fail-closed ở execution |
| Position cap không đúng khi leverage > 1 | Áp trần 25% lên **notional** trước khi đổi sang collateral |

## 3. Chuẩn bị môi trường

Tại PowerShell ở thư mục gốc dự án:

```powershell
uv venv .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

Mọi lệnh bên dưới có thể dùng `freqtrade` sau khi activate môi trường, hoặc dùng đường dẫn rõ ràng ` .\.venv\Scripts\freqtrade.exe`. Script Walk-Forward tự tìm binary Freqtrade nằm cạnh Python đang chạy.

`config.base.json` là cấu hình Hyperliquid/USDC để vận hành. `config.validation.binance.json` dùng Binance/USDT và dữ liệu cục bộ chỉ để kiểm thử, vì nguồn OHLCV lịch sử của Hyperliquid không sẵn qua pipeline Freqtrade trong môi trường này. Không dùng kết quả Binance để tuyên bố hiệu quả live trên Hyperliquid.

## 4. Quy trình dữ liệu, backtest và Hyperopt

### Tải dữ liệu lịch sử

Ví dụ dữ liệu Binance futures cho validation. Hãy tải dài hơn tối thiểu 2.000 nến 15m trước ngày bắt đầu đo để warm-up cả regime 1h.

```powershell
.\.venv\Scripts\freqtrade.exe download-data `
  -c user_data\config\config.validation.binance.json `
  -p BTC/USDT:USDT `
  --timeframes 15m 1h `
  --timerange 20240101-20260828
```

Nếu thay exchange hoặc pair, đổi đồng thời `informative_market_pair` trong config. Không mix `BTC/USDC:USDC` của Hyperliquid với data Binance `BTC/USDT:USDT`.

### Backtest

```powershell
.\.venv\Scripts\freqtrade.exe backtesting `
  -c user_data\config\config.validation.binance.json `
  -s MetaRouter `
  --timerange 20250828-20260828 `
  --export trades `
  --backtest-directory reports\backtests
```

Backtest phải chạy riêng cho `TrendPullback`, `LiquiditySweep`, `RangeReversion` và `MetaRouter`; không coi kết quả một pair hoặc một khoảng thời gian là đủ điều kiện live.

### Hyperopt

`TrendPullback` có parameter trong space `buy`. Các strategy không có `Parameter` (ví dụ `MetaRouter`) không có gì để Hyperopt tối ưu và nên được đánh giá bằng Walk-Forward/backtest với tham số cố định.

```powershell
.\.venv\Scripts\freqtrade.exe hyperopt `
  -c user_data\config\config.validation.binance.json `
  -s TrendPullback `
  --spaces buy `
  --hyperopt-loss SharpeHyperOptLossDaily `
  --epochs 300 `
  --job-workers 1 `
  --timerange 20240101-20250101
```

Giữ `--job-workers 1` trên Windows trừ khi đã kiểm chứng imports strategy chạy được trong worker con. Không dùng kết quả Hyperopt ngắn để live; review file parameter sinh ra trước khi giữ lại.

### Walk-Forward và Monte Carlo

Walk-Forward chạy Hyperopt trên in-sample và backtest trên OOS. Mặc định một worker để ổn định trên Windows; `--workers` chỉ tăng sau khi đã kiểm chứng môi trường đa tiến trình.

```powershell
.\.venv\Scripts\python.exe tools\walkforward.py `
  --strategy TrendPullback `
  --config user_data\config\config.validation.binance.json `
  --timerange 20240101-20260828 `
  --folds 6 --is-months 12 --oos-months 3 `
  --epochs 300 --workers 1

.\.venv\Scripts\python.exe tools\montecarlo.py `
  --trades-csv reports\walkforward_TrendPullback_trades.csv `
  --iterations 5000 --seed 42 `
  --output reports\montecarlo_TrendPullback.md
```

Đã chạy smoke test một fold cho cả `MetaRouter` (nhánh fixed parameter) và `TrendPullback` (Hyperopt + backtest), đồng thời chạy Monte Carlo 100 mẫu. Các report được lưu trong `reports/`. Smoke test ngắn cho kết quả âm và **không đạt** tiêu chí OOS; đó là bằng chứng không được đưa bot sang live khi chưa thực hiện nghiên cứu đủ dài.

## 5. Công cụ vận hành mới

### Healthcheck
```powershell
.\.venv\Scripts\python.exe tools\healthcheck.py

# Kiểm tra các vấn đề:
# - Process running/stale code
# - Config composition
# - Data freshness
# - Risk state (daily/weekly halt)
# - Database health
# - Disk space
# - Strategy imports
```

Exit code 0 = healthy, non-zero = có vấn đề cần xem xét.

### Reconciliation (so sánh signals vs trades)
```powershell
.\.venv\Scripts\python.exe tools\reconcile_dryrun.py `
  --db user_data\tradesv3.dryrun.sqlite `
  --strategy TrendPullback `
  --timerange 20260820-20260829 `
  --output reports\reconciliation.json

# Phát hiện:
# - Matched trades (signal -> execution)
# - Missed signals (blocked by guards)
# - Unexpected trades (no matching signal)
# - Delayed executions
```

Miss rate > 20% cần investigation. Xem denial reasons trong healthcheck.

### Report generator (backtest)
```powershell
.\.venv\Scripts\python.exe tools\report.py `
  user_data\backtest_results\backtest-result-*.zip `
  --output reports\backtest_report.md

# Bao gồm:
# - Total/long/short metrics
# - Temporal breakdown (yearly)
# - Pair breakdown
# - Enter tag breakdown
# - Exit reason summary
# - SHA256 provenance
```

## 6. Kiểm tra bias và regression trước mỗi lần thay đổi

```powershell
.\.venv\Scripts\ruff.exe check . --fix
.\.venv\Scripts\python.exe -m pytest -v

$stamp = Get-Date -Format yyyyMMdd_HHmmss
.\.venv\Scripts\freqtrade.exe lookahead-analysis `
  -c user_data\config\config.validation.binance.json `
  -p BTC/USDT:USDT `
  --strategy-list TrendPullback LiquiditySweep RangeReversion MetaRouter `
  --timerange 20250828-20260828 `
  --minimum-trade-amount 1 `
  --lookahead-analysis-exportfilename "reports\lookahead_analysis_$stamp.csv"
```

Chạy recursive analysis từng strategy vì Freqtrade nhận một `-s` mỗi lần:

```powershell
foreach ($strategy in 'TrendPullback', 'LiquiditySweep', 'RangeReversion', 'MetaRouter') {
  .\.venv\Scripts\freqtrade.exe recursive-analysis `
    -c user_data\config\config.validation.binance.json `
    -s $strategy -p BTC/USDT:USDT `
    --timerange 20250828-20260828 `
    --startup-candle 199 499 999 1999
}
```

Kết quả audit lưu trong file `reports/lookahead_analysis_*.csv`: cả bốn strategy có `has_bias=False`, 20 signals kiểm tra mỗi strategy, không có entry/exit/indicator bias. Recursive analysis sau vá VWAP báo không có indicator lookahead; các cột có đủ warm-up đều 0.000% hoặc sai số làm tròn. Dữ liệu validation hiện có bắt đầu đúng ngày đầu timerange nên log có cảnh báo thiếu phần warm-up rất sớm; khi đánh giá hiệu quả, hãy tải thêm dữ liệu trước timerange thay vì bỏ qua cảnh báo đó.

## 6. Khởi động Dry-Run và cảnh báo Telegram

Tạo file local, không commit (đã được `.gitignore` bảo vệ): `user_data/config/config.telegram.local.json`.

```json
{
  "telegram": {
    "enabled": true,
    "token": "BOT_TOKEN_CUA_BAN",
    "chat_id": "CHAT_ID_CUA_BAN"
  }
}
```

Sau đó chạy dry-run trên Hyperliquid với API key chỉ có quyền giao dịch cần thiết, không quyền rút tiền:

```powershell
.\.venv\Scripts\freqtrade.exe trade `
  -c user_data\config\config.base.json `
  -c user_data\config\config.dryrun.json `
  -c user_data\config\config.telegram.local.json `
  -s MetaRouter
```

Dry-run không gửi lệnh thật nhưng vẫn cần theo dõi spread, slippage, funding, log từ chối guard và Telegram. Để chuyển live, tạo `config.live.json` ngoài Git với `dry_run: false`; không sửa `config.dryrun.json` và không dùng key có quyền rút tiền.

## 7. Checklist an toàn thực tế

### Trước khi chạy backtest/dry-run
- [ ] Đã chạy `ruff`, `pytest`, lookahead và recursive analysis sau mọi thay đổi strategy/config
- [ ] Dữ liệu có đủ warm-up (>= 2000 nến 15m) trước timerange, đúng exchange, futures pair và currency
- [ ] Config composition tested: `freqtrade show-config -c base.json -c overlay.json`
- [ ] Healthcheck pass: `python tools/healthcheck.py`

### Trước khi chấp nhận kết quả backtest
- [ ] Backtest có >= 200 trades trên OOS period
- [ ] Temporal breakdown không có decay nghiêm trọng (PF giảm > 20% year-over-year)
- [ ] Both sides (long/short) có PF >= 1.05 hoặc disable side yếu
- [ ] Walk-Forward với >= 4 folds OOS positive return
- [ ] Monte Carlo ruin probability < 1%
- [ ] Cost stress 0.4% round-trip vẫn PF >= 1.05

### Trước khi khởi động dry-run
- [ ] `dry_run=true`, `force_entry_enable=false`
- [ ] API key tách riêng, không quyền rút tiền, không commit vào Git
- [ ] Telegram/alerts configured và tested
- [ ] Risk state file path writable, không readonly mount
- [ ] Backup DB trước khi start: `cp tradesv3.dryrun.sqlite backups/`
- [ ] Xác minh min stake, tick size, leverage, funding của exchange

### Trong quá trình dry-run (30 ngày tối thiểu)
- [ ] Healthcheck daily: process alive, data fresh, no stale snapshots
- [ ] Reconciliation weekly: miss rate < 20%, unexpected = 0%
- [ ] Performance vs backtest: WR within ±15pp, PF within 20%
- [ ] Guard denial rate < 30%, review reasons nếu cao
- [ ] Risk state checked: no unexpected halts, circuit breaker stable
- [ ] Log review: no repeated errors, no API failures

### Trước khi chuyển live (KHÔNG HIỆN TẠI - chưa có candidate)
- [ ] ❌ **KHÔNG DEPLOY** - chưa có strategy pass Gate Q
- [ ] ❌ Baseline có temporal decay (2026 losing year)
- [ ] ❌ R0/R1 candidates failed recent performance requirements
- [ ] ⏸️ Chờ nghiên cứu strategy mới hoặc market regime change

### Emergency procedures
- [ ] Biết cách stop bot an toàn (xem `docs/RUNBOOK.md`)
- [ ] Biết cách reset risk state nếu halt không đúng
- [ ] Biết cách restore DB từ backup
- [ ] Có contact on-call nếu production
- [ ] Dừng bot ngay khi thấy: lệch execution bất thường, data gap, repeated API errors
