# PLAN: Bot trading crypto DEX dựa trên Freqtrade
Version: 1.0 | Người thực thi: Codex CLI (gpt-luna) | Người review: chủ repo

---

## 0. NGUYÊN TẮC THỰC THI TỰ ĐỘNG (AUTONOMOUS EXECUTION)

1. **Thực thi tuần tự 1 mạch:** Tự động thực hiện từ T01 đến T16 theo thứ tự. Hoàn thành task này → chạy lệnh verify → nếu PASS thì tự động chuyển tiếp ngay sang task tiếp theo mà KHÔNG dừng lại hỏi user.
2. **Xử lý khi lỗi (Self-healing):** Nếu lệnh verify của task fail, đọc lại log lỗi, tự động sửa mã nguồn và verify lại (tối đa 3 lần). Nếu vẫn fail sau 3 lần, ghi chi tiết lỗi vào `QUESTIONS.md` và mới dừng lại.
3. **Quyết định mặc định (Không hỏi user):**
   - Luôn mặc định ưu tiên **Phương án A (Hyperliquid Perp DEX)**. Bỏ qua Phase 5 nếu Phương án A khả dụng.
   - Nếu thiếu dữ liệu lịch sử trên sàn, tự động fallback lấy dữ liệu Binance song song và ghi chú vào `DECISIONS.md`.
4. **Không sửa ngoài phạm vi:** Chỉ tạo và sửa các file được liệt kê trong danh sách `Files` của từng task tương ứng.
5. **Đảm bảo chất lượng:** Tự động chạy `ruff check .` và `pytest -q` sau mỗi task để đảm bảo không phát sinh lỗi cú pháp hay test regression.
---

## 1. MỤC TIÊU & PHẠM VI

Mục tiêu: bot bán tự động giao dịch trên sàn phi tập trung, dùng Freqtrade làm engine (data, backtest, risk, state), có 3 chiến lược module hóa, có validation walk-forward, chạy dry-run tối thiểu 30 ngày trước khi bàn về tiền thật.

Ngoài phạm vi (KHÔNG làm): high-frequency, MEV/sandwich, flash loan, copy-trade ví khác, leverage > 3x, giao dịch coin có liquidity < 1M USD.

Định nghĩa thành công (KPI validation, không phải kỳ vọng lợi nhuận):
- Out-of-sample profit factor ≥ 1.3
- Max drawdown ≤ 20% equity
- Số trade OOS ≥ 200 (nếu ít hơn → kết quả vô nghĩa, không tin)
- Monte Carlo percentile 5% của total return > 0
- Sharpe ≥ 1.0 sau khi trừ phí + slippage + gas mô phỏng

---

## 2. QUYẾT ĐỊNH KIẾN TRÚC

### Phương án A — MẶC ĐỊNH: Perp DEX có API (Hyperliquid)
Freqtrade kết nối trực tiếp qua ccxt. Ít code custom nhất, backtest sát thực tế nhất.
Freqtrade (data + strategy + risk + order) --ccxt--> Hyperliquid API
Điều kiện: `freqtrade list-exchanges` có `hyperliquid`. Nếu không có → nâng version Freqtrade + ccxt, verify lại. Nếu vẫn không → chuyển phương án B và báo cáo.

### Phương án B — Fallback: AMM on-chain (Uniswap v3 / PancakeSwap / Jupiter)
Freqtrade (data từ CEX + strategy) --webhook/REST--> executor service (web3.py) --> DEX router

Freqtrade chạy `dry_run: true` vĩnh viễn, chỉ sinh tín hiệu; executor riêng đặt lệnh on-chain. Bắt buộc có: kiểm tra price impact, slippage tối đa, private RPC (chống MEV), giới hạn approve theo từng lệnh, ví hot riêng ≤ 5% tổng vốn.

**Agent: chỉ triển khai B sau khi có xác nhận của người review.**

---

## 3. CÂY THƯ MỤC ĐÍCH
dex-bot/
├─ user_data/
│ ├─ config/
│ │ ├─ config.base.json
│ │ ├─ config.dryrun.json
│ │ └─ config.live.json.example
│ ├─ strategies/
│ │ ├─ base/BaseRiskStrategy.py
│ │ ├─ TrendPullback.py # Setup A
│ │ ├─ LiquiditySweep.py # Setup B
│ │ ├─ RangeReversion.py # Setup C
│ │ └─ lib/
│ │ ├─ indicators.py
│ │ ├─ regime.py
│ │ ├─ structure.py
│ │ └─ guards.py
│ ├─ hyperopts/
│ └─ notebooks/
├─ executor/ # chỉ dùng ở phương án B
│ ├─ main.py
│ ├─ dex/uniswap_v3.py
│ ├─ risk/limits.py
│ └─ wallet.py
├─ tools/
│ ├─ walkforward.py
│ ├─ montecarlo.py
│ └─ report.py
├─ tests/
├─ .env.example
├─ QUESTIONS.md
├─ DECISIONS.md
└─ README.md


---

## 4. TASK BOARD

Format mỗi task: mục tiêu → files → spec → acceptance → verify command.

### PHASE 0 — Môi trường

**T01. Khởi tạo môi trường**
- Files: `README.md`, `.gitignore`, `.env.example`, `requirements.txt`
- Spec: Python venv, cài freqtrade (bản stable mới nhất), `ruff`, `pytest`. `.gitignore` phải chặn `.env`, `*.key`, `user_data/config/config.live.json`, `user_data/data/`, `user_data/logs/`.
- Acceptance: `freqtrade --version` chạy được; `git status` không thấy file secret.
- Verify: `freqtrade --version && ruff --version && pytest --version`

**T02. Xác nhận sàn hỗ trợ & Cố định phương án**
- Files: `DECISIONS.md`
- Spec: Chạy `freqtrade list-exchanges`. Mặc định chọn exchange `hyperliquid` (Perp DEX). Nếu môi trường chưa có ccxt mới nhất, tự động chạy lệnh update `pip install --upgrade ccxt freqtrade`. Ghi nhận thông số vào `DECISIONS.md`.
- Verify: `freqtrade list-markets --exchange hyperliquid`

**T03. Config nền**
- Files: `user_data/config/config.base.json`, `config.dryrun.json`
- Spec: `dry_run: true`, `stake_currency: USDC` (hoặc theo T02), `stake_amount: unlimited` + `tradable_balance_ratio: 0.9`, `max_open_trades: 3`, `timeframe: 15m`, `dry_run_wallet: 1000`, bật `"trading_mode"` đúng theo T02. Fee override theo số thật ở T02. Bật API server localhost + JWT từ env.
- Acceptance: `freqtrade show-config -c ...` không lỗi; không có secret hardcode.
- Verify: `freqtrade show-config -c user_data/config/config.dryrun.json`

**T04. Tải dữ liệu lịch sử**
- Files: script `tools/download_data.sh`
- Spec: tải 5m, 15m, 1h, 4h cho top 10 cặp, khoảng 3 năm (hoặc tối đa sàn cho phép). Nếu sàn DEX thiếu history → tải song song từ Binance cho mục đích nghiên cứu và **ghi rõ cảnh báo divergence vào DECISIONS.md**.
- Acceptance: `freqtrade list-data` hiện đủ cặp/timeframe.
- Verify: `freqtrade list-data --show-timerange`

### PHASE 1 — Thư viện nền

**T05. `lib/indicators.py`**
- Hàm: `atr(df, n=14)`, `ema(series, n)`, `rsi(series, n)`, `adx(df, n=14)`, `bbands(df, n=20, k=2)`, `vwap_session(df)`, `atr_pct(df, n=14)`, `vol_ma(df, n=20)`.
- Ràng buộc: pandas/numpy hoặc ta-lib nếu đã cài; **không lookahead** — không dùng `shift(-1)`, không dùng dữ liệu nến hiện tại chưa đóng.
- Acceptance: `tests/test_indicators.py` có ≥ 2 test/hàm gồm 1 test giá trị đã biết và 1 test không-NaN-lan-truyền.
- Verify: `pytest tests/test_indicators.py -q`

**T06. `lib/regime.py` — bộ lọc chế độ thị trường**
- Hàm `classify_regime(df_1h) -> Series` trả về `{"trend_up","trend_down","range","chaos"}`:
  - `trend_up`: close > EMA200 và EMA50 > EMA200 và ADX(14) ≥ 20
  - `trend_down`: đối xứng
  - `range`: ADX < 18 và BB width percentile(200) < 0.5
  - `chaos`: `atr_pct` > percentile 95 của 500 nến → **cấm giao dịch**
- Acceptance: test trên dữ liệu tổng hợp (chuỗi tăng tuyến tính → trend_up; sin wave → range).
- Verify: `pytest tests/test_regime.py -q`

**T07. `lib/structure.py` — cấu trúc giá**
- Hàm:
  - `swing_points(df, left=3, right=3)` → cột `is_swing_high/low` (right lookback đã đóng, không lookahead)
  - `last_impulse_leg(df)` → (start_idx, end_idx, direction)
  - `fib_zone(leg, lo=0.382, hi=0.618)`
  - `detect_fvg(df, atr_mult=1.5)` → list gap (imbalance 3 nến, body nến giữa > 1.5×ATR)
  - `sweep_level(df, level, max_bars_back=3)` → True nếu wick vượt level rồi đóng lại trong vùng trong ≤ 3 nến
  - `prev_session_range(df, session="asia", tz="UTC")` → (high, low)
- Acceptance: mỗi hàm ≥ 1 test với dữ liệu dựng tay có kết quả biết trước.
- Verify: `pytest tests/test_structure.py -q`

**T08. `lib/guards.py` — bộ chặn thực thi**
- Hàm:
  - `spread_ok(ticker, max_bps=15)`
  - `slippage_ok(orderbook, notional, max_bps=30)` — tính price impact từ depth
  - `liquidity_ok(pair_meta, min_24h_vol_usd=1_000_000)`
  - `funding_ok(funding_rate, max_abs=0.0005)` (nếu perp)
  - `news_blackout(now, windows)` — đọc từ `user_data/config/blackout.json`
  - `daily_loss_halt(equity_start_day, equity_now, max_pct=2.0)`
- Acceptance: test biên (đúng ngưỡng, trên ngưỡng, dưới ngưỡng).
- Verify: `pytest tests/test_guards.py -q`

### PHASE 2 — Base strategy & risk

**T09. `base/BaseRiskStrategy.py`**
- Spec: class kế thừa `IStrategy`, chứa toàn bộ money management, các strategy con chỉ định nghĩa entry/exit signal.
  - `custom_stake_amount()`: position size theo **fixed fractional risk**
    `size = (equity * risk_pct) / (entry - stop_price)`, `risk_pct = 0.005`; kẹp bởi min notional và `max_position_pct = 0.25` equity.
  - `custom_stoploss()`: SL ban đầu = `swing ± 1.0×ATR14`; sau khi đạt +1R → về breakeven; sau +1.5R → trailing bằng `2×ATR` hoặc chandelier.
  - `custom_exit()`: TP1 = 1.0R chốt 50% (dùng `adjust_trade_position` partial exit), phần còn lại trail. Hard time-stop: đóng nếu sau 24 nến chưa đạt +0.5R.
  - `confirm_trade_entry()`: gọi toàn bộ guards ở T08; trả False nếu bất kỳ guard fail; log lý do.
  - `protections`: CooldownPeriod 3 nến; StoplossGuard 2 SL/6h → dừng 12h; MaxDrawdown 10% → dừng 24h; LowProfitPairs.
  - Hằng số risk đặt ở đầu file trong dict `RISK` có comment, không rải rác magic number.
- Acceptance: `freqtrade list-strategies` nhận diện; test unit cho `custom_stake_amount` với 3 bộ input.
- Verify: `pytest tests/test_risk.py -q && freqtrade list-strategies`

### PHASE 3 — Ba chiến lược

Nguyên tắc chung mọi strategy: `process_only_new_candles = True`, `use_exit_signal = True`, `can_short` theo T02, mọi informative pair lấy qua `@informative` decorator (không tự merge tay), **không được để lookahead**.

**T10. Setup A — `TrendPullback.py` (trend following, WR kỳ vọng 40–50%, RR 2–3)**
Long entry, tất cả điều kiện AND:
1. `regime_1h == trend_up` (T06)
2. Giá đã pullback: low chạm vùng `fib_zone(0.382–0.618)` của impulse leg gần nhất HOẶC chạm EMA21 (15m)
3. Nến trigger đóng lại **trên** EMA21 15m với body > 0.5×ATR
4. `RSI14` cắt lên trên 50 (nến trước < 50)
5. `volume > 1.2 × vol_ma20`
6. Không có swing low mới thấp hơn swing low trước (cấu trúc chưa vỡ)
7. Khoảng cách tới SL ≥ 0.5×ATR (tránh SL quá sát) và ≤ 3×ATR
SL: swing low gần nhất − 1.0×ATR. TP1 = 1R. Còn lại trail.
Short: đối xứng với `trend_down`.

**T11. Setup B — `LiquiditySweep.py` (sweep + FVG, WR 45–55%, RR ≥ 2)**
Long entry:
1. `regime_1h != chaos`
2. Có `sweep_level` xuống dưới `prev_session_range.low` (hoặc PDL) rồi đóng lại phía trên trong ≤ 3 nến
3. Nến displacement ngay sau đó: body > 1.5×ATR, đóng trên mức bị sweep
4. Displacement tạo bullish FVG → **entry limit tại 50% FVG**, hủy lệnh nếu không fill trong 4 nến
5. SL = đáy wick sweep − 0.2×ATR
6. TP1 = đối diện session range hoặc FVG ngược đầu tiên; yêu cầu RR tính trước ≥ 2, nếu < 2 → bỏ setup
7. Chỉ giao dịch trong killzone cấu hình được (`sessions.json`), mặc định London 07–10 UTC, NY 12–15 UTC

**T12. Setup C — `RangeReversion.py` (mean reversion, WR kỳ vọng 60–72%, RR ~0.8–1.0)**
Long entry:
1. `regime_1h == range`
2. close ≤ BB lower(20,2) 15m
3. `RSI14 < 30` (hoặc `RSI2 < 10`)
4. z-score khoảng cách tới VWAP session ≤ −2.0
5. Không có 2 nến giảm liên tiếp với body > 2×ATR (loại trừ breakdown thật)
Exit: TP tại BB mid / VWAP. SL = 1.5×ATR. Time-stop 12 nến.
Cấm chạy khi `regime` chuyển sang trend (thoát ngay ở nến đầu tiên regime đổi).

Acceptance cho T10–T12 (mỗi task):
- `freqtrade backtesting -s <Name> --timerange <2 năm> --breakdown month` chạy không lỗi
- `freqtrade lookahead-analysis -s <Name>` **không phát hiện bias** → điều kiện bắt buộc, fail thì task fail
- `freqtrade recursive-analysis -s <Name>` ổn định
- Số trade ≥ 100 trên timerange test
- Báo cáo bảng: trades, WR, avg RR, profit factor, max DD, expectancy
Verify: dán nguyên output backtest + lookahead-analysis.

**T13. Strategy tổ hợp `MetaRouter.py`**
- Spec: chọn strategy theo regime — trend_up/down → Setup A; range → Setup C; Setup B chạy song song nhưng giới hạn 1 vị thế. Tổng `max_open_trades = 3`, không quá 2 vị thế cùng chiều, không quá 1 vị thế trên nhóm coin tương quan > 0.8 (bảng correlation tính offline, lưu `correlation.json`).
- Acceptance: backtest MetaRouter tốt hơn hoặc bằng trung bình 3 strategy đơn lẻ về profit factor **và** thấp hơn về max DD.

### PHASE 4 — Validation (KHÔNG BỎ QUA)

**T14. `tools/walkforward.py`**
- Spec: chia timerange thành N=6 fold; mỗi fold: hyperopt trên IS (12 tháng) → test OOS (3 tháng), rolling. Chỉ hyperopt tối đa **6 tham số** (đánh dấu `IntParameter/DecimalParameter` trong strategy), `--spaces buy sell`, epochs 300, loss `SharpeHyperOptLossDaily`. Xuất CSV + markdown tổng hợp.
- Acceptance: file `reports/walkforward_<strategy>.md` có bảng từng fold; kết luận PASS/FAIL theo KPI mục 1.

**T15. `tools/montecarlo.py`**
- Spec: bootstrap resample chuỗi trade OOS 5000 lần → phân phối total return, max DD, risk of ruin (ngưỡng −30%).
- Acceptance: report có percentile 5/50/95 và risk of ruin < 1%.

**T16. Stress test phí & slippage**
- Spec: chạy lại backtest với fee ×2, slippage 30bps, 50bps; với phương án B thêm gas cố định/lệnh.
- Acceptance: PF ở kịch bản 30bps vẫn ≥ 1.1. Nếu strategy sụp ở 30bps → **loại strategy đó**, ghi vào DECISIONS.md.

### PHASE 5 — Execution on-chain (chỉ khi phương án B, cần duyệt)

**T17. `executor/wallet.py`** — load key từ env hoặc keystore mã hóa, không log, không ghi ra file, hàm `sign_and_send(tx)` bắt buộc qua private RPC, có nonce manager và replace-by-fee.
**T18. `executor/dex/uniswap_v3.py`** — quote qua Quoter, tính price impact, `exactInputSingle` với `amountOutMinimum` theo slippage tối đa, `deadline` ≤ 60s, approve theo đúng số lượng từng lệnh (không infinite approve).
**T19. `executor/risk/limits.py`** — hạn mức: notional/lệnh, số lệnh/giờ, tổng exposure, whitelist token address (hardcode, verify checksum), circuit breaker khi 3 tx fail liên tiếp.
**T20. `executor/main.py`** — nhận webhook từ Freqtrade, idempotency key theo trade_id, retry có backoff, ghi journal SQLite mọi ý định + kết quả tx.
Acceptance T17–T20: chạy testnet end-to-end 20 lệnh, 0 lệnh vượt slippage cấu hình, journal khớp on-chain.

### PHASE 6 — Vận hành

**T21. Telegram + logging** — bật Telegram, cấu hình `notification_settings`; log JSON có rotate; alert riêng cho: guard chặn lệnh, halt daily loss, drawdown protection kích hoạt, tx fail.
**T22. Health check** — cron kiểm tra bot alive, data mới nhất < 2 nến, chênh giá DEX vs CEX < 1% (nếu >1% → pause), balance ví.
**T23. Dry-run 30 ngày** — chạy `config.dryrun.json`, mỗi tuần xuất report so sánh dry-run vs backtest cùng kỳ. Sai lệch WR > 15 điểm phần trăm → điều tra trước khi đi tiếp.

### PHASE 7 — Checklist trước khi bàn tới tiền thật (người review tự tick, agent không tự làm)
- [ ] Toàn bộ KPI mục 1 PASS trên OOS
- [ ] lookahead-analysis clean cho mọi strategy đang dùng
- [ ] Dry-run 30 ngày khớp backtest trong ngưỡng
- [ ] Stress 30bps PASS
- [ ] Ví hot riêng, vốn ≤ 5% tổng, không chứa NFT/token khác
- [ ] Có kill switch thủ công test thành công
- [ ] Backup config + DB, khôi phục thử thành công
- [ ] Vốn khởi điểm thật = 10% kế hoạch trong 2 tuần đầu

---

## 5. BẢNG THAM SỐ RISK MẶC ĐỊNH (điểm bắt đầu, cần backtest)

| Tham số | Giá trị | Ghi chú |
|---|---|---|
| risk_per_trade | 0.5% equity | không tăng khi thua |
| max_open_trades | 3 | |
| max_position_pct | 25% equity | kể cả khi công thức size cho lớn hơn |
| daily_loss_halt | 2% | dừng tới 00:00 UTC |
| weekly_loss_halt | 5% | dừng tới thứ Hai |
| leverage | ≤ 2x (nếu perp) | không dùng cross toàn ví |
| max_slippage | 30 bps | perp; AMM tính theo price impact |
| min_24h_volume | 1M USD | |
| ATR% chaos cut | percentile 95/500 nến | |
| RR tối thiểu Setup B | 2.0 | |

---

## 6. NHỮNG SAI LẦM PHẢI TRÁNH (agent kiểm tra lại mỗi task)

- Lookahead bias: dùng nến chưa đóng, `shift(-n)`, resample sai chiều, `merge_informative` thủ công lệch timeframe.
- Overfit: hyperopt > 6 tham số, epochs quá nhiều, chọn kết quả tốt nhất trên IS mà không có OOS, tối ưu trên < 100 trade.
- Survivorship bias: chỉ backtest coin hiện còn sống/đang top.
- Bỏ phí: DEX có phí pool + gas + price impact + funding; nếu backtest lãi mỏng hơn tổng phí thì nó là lỗ.
- Martingale/DCA vô hạn khi thua — cấm tuyệt đối.
- Tin vào win rate mà bỏ qua expectancy: `E = WR×avgWin − (1−WR)×avgLoss`. Chỉ `E > 0` sau phí mới có nghĩa.

---

## 7. MẪU PROMPT GIAO VIỆC CHO GPT-LUNA (copy từng task)
Đọc PLAN_DEX_BOT.md, phần "NGUYÊN TẮC LÀM VIỆC CHO AGENT" và task T05.
Chỉ thực hiện T05. Không sửa file nào ngoài danh sách Files của T05.
Trước khi code: đọc các file liên quan bằng tool đọc file, không dựa vào trí nhớ.
Sau khi code: chạy lệnh Verify của task, dán output.
````

Thứ tự chạy: T01 → T04 (môi trường/data), T05 → T09 (thư viện + risk), T10 → T13 (chiến lược), T14 → T16 (validation — đây là phase quyết định, đừng bỏ), rồi mới tới execution.

Một lưu ý về kỳ vọng: nếu sau T14–T16 cả ba setup đều fail KPI thì kết quả đúng là **không chạy live**, chứ không phải nới tham số cho đến khi backtest đẹp. Đó là cách phổ biến nhất để mất tiền với bot.