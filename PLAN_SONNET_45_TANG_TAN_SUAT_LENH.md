# Kế hoạch tự trị vòng 2 cho Claude Sonnet 4.5

> Mục tiêu: sửa nền tảng đo lường, hardening bot và chỉ sau đó mới nghiên cứu phục hồi hiệu quả ngoài mẫu (OOS). Thời lượng dự kiến 6–12 giờ máy chạy, có thể lâu hơn tùy Hyperopt/Walk-Forward. Kế hoạch này thay thế toàn bộ kế hoạch tăng tần suất vòng trước.

## Prompt giao việc nguyên văn

Hãy thực hiện toàn bộ file này từ trên xuống dưới. Làm liên tục, tự xử lý lỗi kỹ thuật trong phạm vi dự án và không dừng để hỏi sau từng phase. Mỗi phase chỉ được đánh dấu hoàn thành khi các acceptance criteria của phase đó đã qua. Nếu một candidate không qua gate, ghi bằng chứng, loại candidate và tiếp tục nhánh hợp lệ tiếp theo; tuyệt đối không nới gate để tạo kết quả đẹp.

Các giới hạn bắt buộc:

- Đọc và tuân thủ `AGENTS.md`/`C:\Users\MAITAM-DNI\.codex\RTK.md`; mọi lệnh shell phải bắt đầu bằng `rtk`.
- Không chạy `freqtrade trade`, không khởi động thêm bot và không dừng process bot đang chạy.
- Không sửa/xóa database dry-run, file log, dữ liệu market hay artifact cũ.
- Không dùng secret thật, không in secret, không commit `.env`.
- Không dùng lệnh Git phá hủy; worktree chưa có commit gốc nên không được giả định `git diff` là đủ để tìm thay đổi.
- Không promotion live. Kết quả cao nhất chỉ được là `READY FOR DRY-RUN REVIEW`.
- Không thay đổi pairlist/timeframe để che một candidate yếu. Không tối ưu trên holdout cuối.
- Dùng `apply_patch` khi sửa file thủ công. Giữ thay đổi hiện có không liên quan.
- Sau mỗi phase, cập nhật `reports/pro_hardening/PROGRESS.md`, gồm command, exit code, artifact, metric và quyết định.
- Khi command chạy dài, theo dõi định kỳ; không tự dừng chỉ vì chưa có output.

## 0. Sự thật đã được kiểm tra — không được dùng số cũ

### Tình trạng kỹ thuật ban đầu

- `pytest`: 63 tests pass; `ruff`: pass; `compileall`: pass; dependency check bằng `uv pip check`: pass.
- Dữ liệu có 5 cặp Binance futures, timeframe 15m và informative 1h từ 2024-01-01 đến 2026-08-28. Chưa có dữ liệu 5m cho `--timeframe-detail`.
- Có một dry-run cũ được khởi động từ 2026-08-28 với `MetaRouter`; process đã load code/config cũ và Python không tự reload. Không được dùng log của process đó để chứng minh code mới đang chạy, không dừng nó trong task này.
- Report lookahead ngày 2026-08-28 có trước thay đổi code ngày 2026-08-29, nên là artifact cũ, không đủ cho verdict cuối.

### Baseline thực tế đọc trực tiếp từ ZIP

`TrendPullback`, full period 2024-01-01 đến 2026-08-28:

| Metric | Giá trị đúng |
|---|---:|
| Trades | 989 |
| Trades/day | 1.04 |
| Profit factor | 1.0524 |
| Return | 14.0186% |
| Max account drawdown | 23.8643% |
| Sharpe | 0.478 |
| Long | 492 trades, PF 0.8756, return -17.84% |
| Short | 497 trades, PF 1.2568, return +31.86% |

Temporal decay phải được coi là blocker chính:

- 2024: long PF 1.165, short PF 1.498.
- 2025: long PF 0.786, short PF 1.279.
- 2026: long PF 0.572, short PF 1.013.
- Mọi quý từ 2025-Q3 đến 2026-Q3 đều có tổng PF dưới 1.

Hai candidate tăng entry ở vòng trước đều fail: Candidate A PF 1.0289/DD 27.88%; Candidate B PF 1.0346/DD 26.45%. `MetaRouter` short-only có 497 trades, PF 1.2520, return 31.13%, DD 7.29%, Sharpe 1.056 trên full period, nhưng chưa chứng minh OOS/recent robustness.

### Những lỗi bắt buộc sửa trước nghiên cứu chiến lược

1. `tools/report.py` đang đọc sai schema Freqtrade 2026.7:
   - Phải dùng `trade_count_long`/`trade_count_short`, không phải `trades_long`/`trades_short`.
   - `profit_total` là ratio; phần trăm phải nhân 100 hoặc dùng field `_pct` đúng schema.
   - Max DD phần trăm phải lấy `max_drawdown_account`; `max_drawdown_abs` là stake currency.
   - Breakdown đúng là `results_per_enter_tag` và `results_per_pair`.
   - CLI thiếu mode phải trả exit code khác 0.
2. Unit test report đang dùng fixture tự chế sai schema nên tạo false confidence.
3. `tools/walkforward.py` đang compound `profit_ratio` theo từng trade, làm sai equity/DD khi trade overlap hoặc stake thay đổi; Sharpe theo trade không được so với Sharpe portfolio hằng ngày.
4. `tools/montecarlo.py` bootstrap IID phá hủy regime clustering; fallback coi `profit_abs` là ratio là sai đơn vị.
5. `BaseRiskStrategy` gọi `dp.ticker()`/`dp.orderbook()` trực tiếp trong `confirm_trade_entry`, gây network I/O trên callback timing-critical; kiểm tra funding hiện fail-open; volume fallback có thể đem base volume so với ngưỡng USD.
6. `use_custom_stoploss=False` trong khi tài liệu nói custom stop đang bật; trailing và custom stop chưa có single source of truth.
7. Circuit breaker chỉ ở memory, mất khi restart; chưa có weekly loss halt. Protection thiếu `trade_limit` tường minh và MaxDrawdown chưa dùng equity mode.
8. `.env.example` dùng sai naming convention; README chạy riêng `config.dryrun.json` dù file này thiếu exchange và sẽ lỗi. `.gitignore` chưa chặn DB/WAL/log/report runtime. Chưa có lockfile/CI/healthcheck.

## 1. Gate cứng và quy tắc quyết định

### Gate R — độ tin cậy của phép đo

Phải qua trước mọi tối ưu:

- Parser khớp chính xác số từ ít nhất 2 ZIP thật với tolerance `1e-8` cho ratio và `1e-4` cho phần trăm.
- Report thể hiện rõ unit: ratio, percent, stake currency; không đoán field hoặc silently default về 0.
- Report có total/long/short/pair/tag/year/quarter/month và provenance: ZIP, strategy, timerange, config, generated_at.
- Command lỗi hoặc schema thiếu field bắt buộc phải trả non-zero và message dễ hiểu.
- Walk-forward dùng daily equity/returns từ cash-flow đúng đơn vị; ghi rõ giới hạn khi không tái dựng được equity chính xác.

### Gate S — an toàn vận hành

- Không network I/O trực tiếp trong callback xác nhận entry; callback chỉ đọc snapshot cache có timestamp.
- Snapshot stale/missing phải fail closed với reason có metric; funding unknown không được mặc định cho qua.
- Daily và weekly loss state tồn tại qua restart, ghi atomically, có timezone UTC và recovery test.
- Một cơ chế stop chủ đạo được chọn và tài liệu/code/config thống nhất.
- Sizing không vượt `max_risk_per_trade`, notional cap, available stake và exchange precision trong test.
- Config compose, env override, DB/log paths và secret hygiene có automated test.

### Gate Q — chất lượng candidate

Candidate chỉ được chuyển sang validation tốn thời gian nếu đồng thời đạt:

- Full period: trades >= 450, PF >= 1.15, return > 0, expectancy > 0, max account DD <= 15%, Sharpe daily >= 0.75.
- Recent 2026-01-01 đến 2026-08-28: trades >= 100, PF >= 1.10, return > 0, DD <= 12%.
- Walk-forward: ít nhất 4/6 fold test có return dương; không fold nào PF < 0.90; aggregate OOS >= 200 trades, PF >= 1.20, DD <= 15%, daily Sharpe >= 1.0.
- Mỗi side active có >= 100 trades và PF >= 1.05; nếu side fail thì phải tắt side, không dùng side thắng để che side thua.
- Không pair nào có >= 50 trades và PF < 0.90; leave-one-pair-out không làm aggregate PF tụt dưới 1.05.
- Cost stress 0.4% round-trip vẫn PF >= 1.05 và DD <= 20%.
- Lookahead không bias trên mọi signal thực sự trigger; recursive variance nằm trong ngưỡng đã ghi.
- Block Monte Carlo: probability of ruin < 1%, max-DD p95 <= 25% theo định nghĩa ruin được khóa trước khi chạy.

### Gate O — readiness vận hành

Gate O không cho phép live. Chỉ gắn `READY FOR DRY-RUN REVIEW` khi R, S, Q đều qua, healthcheck pass và checklist dry-run/reconciliation/alert đầy đủ. Nếu không, verdict là `RESEARCH ONLY` hoặc `NO ROBUST CANDIDATE`.

## 2. Phase 0 — inventory, snapshot và bảo vệ trạng thái

Mục tiêu: tạo bằng chứng trước khi sửa, không làm ảnh hưởng bot cũ.

1. Ghi version Python/Freqtrade/uv/OS, `git status --short`, hash SHA256 của strategy/config/tool/docs quan trọng.
2. Liệt kê process Freqtrade và command line. Nếu đã có `trade`, chỉ ghi PID/start time/command; không start/stop.
3. Chạy smoke read-only: pytest, ruff, compileall, `uv pip check`, `list-strategies`, compose config base+backtest và base+dryrun.
4. Kiểm tra `.env`, database và log có được ignore không nhưng không đọc nội dung secret.
5. Tạo `reports/pro_hardening/INVENTORY.md`, `source_manifest.sha256`, `PROGRESS.md`.

Acceptance: có snapshot đủ để phân biệt artifact/code trước và sau; process cũ được ghi rõ; không file runtime nào bị sửa.

## 3. Phase 1 — sửa report parser và dựng test bằng artifact thật

File chính: `tools/report.py`, `tests/test_tools.py`; được tách test mới nếu giúp rõ schema.

1. Mở đúng ZIP baseline và ít nhất một ZIP candidate, đọc `backtest-result.json` bên trong.
2. Viết adapter schema rõ ràng cho Freqtrade 2026.7. Nếu muốn hỗ trợ schema cũ, version-detect tường minh; không dùng chuỗi `.get(..., 0)` che lỗi.
3. Chuẩn hóa model nội bộ có unit trong tên field: `return_ratio`, `return_pct`, `max_drawdown_ratio`, `max_drawdown_pct`, `profit_abs_stake`.
4. Parse total/long/short, pair, enter-tag, exit reason, monthly/yearly/quarterly và trades thô.
5. Tạo sanitized fixture từ một ZIP thật: giữ schema/metrics/trade mẫu, không nhúng secret hay file quá lớn. Kiểm tra fixture bằng giá trị raw đã khóa.
6. Test malformed ZIP, missing strategy, missing mandatory key, zero trades, CLI no-mode, output path và numeric tolerance.
7. Report phải ghi source ZIP SHA256 và không overwrite artifact: nếu output đã có thì fail hoặc tạo tên mới có timestamp.

Các số regression tối thiểu phải assert cho baseline: 989 trades; 492 long; 497 short; PF 1.05241169; return 14.0186% gần đúng; max account DD 23.8643% gần đúng.

Acceptance: Gate R phần parser qua; `pytest`/`ruff` pass; report mới không còn 0 long/short, 0.14% return hoặc 353.06% DD.

## 4. Phase 2 — errata và tái tạo baseline/candidate reports

1. Không sửa artifact lịch sử; tạo `reports/pro_hardening/ERRATA.md` chỉ rõ report/kết luận cũ nào sai, field sai, số đúng và nguồn ZIP.
2. Tạo report mới cho baseline, Candidate A, Candidate B và MetaRouter short-only.
3. Thêm bảng theo năm/quý/tháng, side, pair, tag; đánh dấu sample nhỏ.
4. Sửa `DECISIONS.md` để không gán PF của MetaRouter tag sang TrendPullback và không gọi baseline là ổn định.
5. Lập automated assertion rằng mọi quý 2025-Q3..2026-Q3 baseline PF < 1 như bằng chứng decay hiện có.

Acceptance: tất cả số công bố truy ngược được đến ZIP/hash; kết luận vòng trước được đính chính nhưng artifact cũ vẫn nguyên vẹn.

## 5. Phase 3 — sửa Walk-Forward thành công cụ OOS đáng tin

File chính: `tools/walkforward.py`, tests và tài liệu CLI.

1. Phân tách train/test tuyệt đối theo timestamp UTC; có embargo ít nhất bằng startup candle + max lookback để tránh boundary leakage.
2. Mỗi fold có thư mục riêng, parameter file riêng và manifest train/test. Fail nếu thiếu đúng số fold yêu cầu; không silently dừng sớm.
3. Thêm `--random-state`, `--min-trades`, `--enable-protections`, timeout và resume idempotent. Không tái dùng cache giữa timerange khi không chứng minh cache key đúng.
4. Xác minh Hyperopt thực sự export parameter được fold test load. Log hash của source/config/parameter cho cả train và test.
5. Không compound trade ratios. Ưu tiên equity/cumulative profit series từ kết quả Freqtrade; chuẩn hóa daily return và tính Sharpe/Sortino/DD trên daily equity. Nếu exact equity không tái dựng được do overlap/stake, báo metric unavailable thay vì bịa.
6. Aggregate OOS bằng nối chronological daily PnL/equity; không trung bình đơn giản PF/DD giữa fold.
7. Test unit với overlapping trades, stake khác nhau, no-trade fold, missing export, early termination, deterministic seed và resumed run.
8. Chạy smoke 2 folds, 5–10 epochs chỉ để test plumbing; ghi `SMOKE ONLY`, không dùng performance để promotion.

Acceptance: Gate R hoàn tất; 2 lần smoke cùng seed cho manifest/metrics giống nhau trong tolerance; mọi fold train/test/embargo không overlap.

## 6. Phase 4 — nâng Monte Carlo từ IID lên block/regime bootstrap

File chính: `tools/montecarlo.py` và tests.

1. Xóa fallback `profit_abs -> profit_ratio`. Thiếu ratio/cash-flow hợp lệ phải fail.
2. Hỗ trợ moving-block bootstrap theo daily portfolio returns; block mặc định 7 ngày, sensitivity 3/14/28 ngày.
3. Có thể stratify theo regime/tháng nhưng không làm mất ordering trong block. IID chỉ là diagnostic được gắn nhãn, không dùng cho gate.
4. Khóa trước `starting_equity`, ruin threshold, number of paths, seed và horizons. Báo p50/p90/p95/p99 DD, terminal return, loss probability, ruin probability.
5. Test deterministic, all-win/all-loss, clustered losses, invalid unit, short input, NaN/Inf.
6. Chạy smoke 1,000 paths để kiểm tra; run final 10,000 chỉ cho candidate qua Gate Q sơ bộ.

Acceptance: clustered-loss fixture có tail risk xấu hơn IID hợp lý; command invalid data trả non-zero.

## 7. Phase 5 — execution guard không network trong callback

File chính: `BaseRiskStrategy.py`, `lib/guards.py`; có thể thêm module snapshot nhỏ, không tạo service lớn nếu chưa cần.

1. Tách collector và evaluator:
   - Collector cập nhật orderbook top levels, quote volume/notional, funding rate, timestamp và error state bên ngoài đường xác nhận entry.
   - `confirm_trade_entry` chỉ đọc immutable snapshot/cache và chạy O(1), không gọi ticker/orderbook/funding API.
2. Dùng monotonic/UTC timestamp nhất quán, cấu hình TTL; stale, missing, NaN hoặc exchange error đều deny entry với reason counter.
3. Liquidity dùng quote notional có unit rõ. Không so base volume với USD threshold.
4. Funding dùng `dp.funding_rate(pair)` ở collector hoặc nguồn tương đương đã xác minh; unknown phải fail closed.
5. Spread/slippage tính theo side, giá proposed và depth cần thiết cho estimated stake. Thêm boundary tests cho long/short.
6. Rate-limit logs theo reason để không spam; xuất counters cho healthcheck.
7. Nếu framework không có lifecycle hook phù hợp, dùng analyzed dataframe columns/cached refresh hợp lệ; ghi rõ design, không lén network trong callback.

Acceptance: monkeypatch network methods để raise nếu callback chạm tới; callback vẫn chạy bằng cache, stale cache bị chặn; latency unit benchmark cục bộ p99 dưới 10 ms.

## 8. Phase 6 — persistent risk, stop semantics và protections

1. Chọn một stop architecture:
   - Nếu bật `custom_stoploss`, đặt `use_custom_stoploss=True` và tắt trailing cạnh tranh; callback trả khoảng cách tương đối so với current rate đúng semantics Freqtrade.
   - Hoặc giữ trailing/hard stop và xóa/đánh dấu callback custom không sử dụng.
   Không được vừa mô tả cả hai là active.
2. Kiểm tra sizing theo stop thực sự active, leverage, contract size, precision, min/max stake. Property tests: loss tại stop không vượt risk budget ngoài rounding/slippage tolerance đã khóa.
3. Tạo risk-state persistent atomic cho daily realized PnL, weekly realized PnL, peak equity, halt reason, schema version và updated_at UTC. Dùng temp + atomic replace và lock; corrupted state fail closed.
4. Reset boundary theo UTC; test restart, day/week rollover, duplicate trade event, partial exits và corrupted file.
5. Daily/weekly halt có hysteresis/manual recovery được tài liệu hóa; không tự reset chỉ vì restart.
6. Khai báo protection tường minh: `trade_limit`, lookback, stop duration. Với MaxDrawdown dùng equity/drawdown mode phù hợp phiên bản hiện tại. Bật protections trong mọi backtest validation.
7. Xác định single source of truth cho partial exit/DCA. Nếu position adjustment active, test max adjustments, min stake, duplicate candle và live/backtest frequency caveat; nếu không cần thì tắt.
8. Thêm emergency-exit matrix cho stale data, exchange unavailable, state corruption và API error; không thực hiện network/mutation external trong unit test.

Acceptance: Gate S risk/stop/protection qua; test process-restart chứng minh halt vẫn tồn tại; docs và `show-config` phản ánh đúng cơ chế active.

## 9. Phase 7 — config, secret, reproducibility và CI

1. Sửa `.env.example` sang dạng `FREQTRADE__SECTION__KEY`, ví dụ nested key bằng double underscore. Không đưa credential thật.
2. README luôn compose `config.base.json` trước environment overlay. Thêm automated subprocess test cho base+backtest và base+dryrun; test dryrun-only phải fail với message dự kiến hoặc không còn được tài liệu khuyên dùng.
3. `.gitignore`: `.env*` ngoại trừ example, `*.sqlite*`, `*.db*`, `*.log*`, runtime reports/cache, credential/config private; không ignore fixture/report source cần versioning một cách quá rộng.
4. Pin dependency reproducibly bằng lockfile phù hợp `uv`; giữ `requirements.txt` như input nếu cần. Ghi Python/Freqtrade version đã kiểm thử.
5. Thêm CI tối thiểu: install locked deps, pytest, ruff, compileall, config validation và list-strategies. Job không cần exchange/network/secret.
6. Tạo command `tools/healthcheck.py` read-only kiểm tra config composition, data freshness, strategy import, risk-state health, snapshot freshness, DB/log path, disk space và PID conflict. JSON output + exit code severity.
7. Log structured JSON/rotating file, redaction secret, alert abstraction. Chỉ tạo mock Telegram/webhook test; không gửi message thật.

Acceptance: clean install từ lock pass CI; config/env tests pass; healthcheck offline có deterministic fixture; DB/WAL/log/private config được ignore.

## 10. Phase 8 — nghiên cứu strategy mới, giữ baseline bất biến

Không tiếp tục nới entry trong `TrendPullback`. Tạo strategy nghiên cứu riêng, ví dụ `RobustTrend`, kế thừa safety layer đã sửa. `TrendPullback` và artifact vòng trước là control, không bị chỉnh để khớp kết quả.

Thesis: long side đã decay mạnh; bắt đầu short-only, sau đó chỉ mở lại long nếu long tự qua gate. Candidate matrix phải nhỏ và causal:

- R0: MetaRouter `trend_short` hiện có, tái chạy bằng measurement/protection đúng.
- R1: R0 + DMI directional separation (`-DI > +DI`) với threshold duy nhất.
- R2: R1 + EMA slope normalized by ATR để loại sideways; không dùng future value.
- R3: R1 + regime persistence 2–3 candles để giảm flip-flop.
- R4: R2 + bounded recent-pullback validity 1–2 candles, nhưng không nới đồng thời điều kiện khác.

Quy tắc:

1. Mỗi candidate chỉ khác control một hypothesis, có unit tests synthetic cho trigger/non-trigger/crossover/lookback/NaN/startup.
2. Tối đa 6 parameter tối ưu; parameter có prior/range hẹp, economic rationale rõ. Không optimize stop, ROI, entry, pair selection cùng lúc.
3. Dùng full period và recent 2026 như screening, nhưng chưa gọi OOS. Candidate fail Gate Q screening bị loại trước Hyperopt dài.
4. Long là sleeve riêng. Chỉ bật nếu long recent PF >= 1.10, DD contribution hợp lý và OOS độc lập qua gate; nếu không giữ short-only.
5. Mọi backtest validation bật protections và dùng cùng config/fee assumptions.

Acceptance: chọn tối đa 2 candidate screening; nếu không candidate nào qua, ghi `NO ROBUST CANDIDATE` và vẫn hoàn tất hardening/docs, không ép Hyperopt.

## 11. Phase 9 — temporal split và holdout khóa trước

Khóa split trong `reports/pro_hardening/EXPERIMENT_SPEC.md` trước khi chạy tối ưu:

- Development/train: 2024-01-01 đến 2025-06-30.
- Validation: 2025-07-01 đến 2025-12-31.
- Final holdout: 2026-01-01 đến 2026-08-28.
- Walk-forward 6 folds expanding hoặc rolling, test window tối thiểu 90 ngày, embargo theo Phase 3.

Tính timerange half-open/exclusive đúng cách để không trùng ngày biên. Hash spec. Sau khi mở holdout, không sửa candidate/range/parameter/gate. Nếu fail holdout, kết luận fail; muốn nghiên cứu tiếp phải tạo experiment ID mới và holdout mới trong tương lai.

Acceptance: script xác minh không overlap/gap ngoài embargo; spec/hash xuất hiện trong mọi manifest.

## 12. Phase 10 — Hyperopt đa seed, giới hạn overfit

Chỉ chạy cho tối đa 2 candidate qua screening. Dùng `MultiMetricHyperOptLoss`, `--spaces buy`, protections, cùng pair/timeframe/config và train range đã khóa.

1. Chạy 3 seed: 42, 1337, 20260829; tối thiểu 200 epochs/seed. Dự kiến 2–4 giờ.
2. Mỗi run lưu command, elapsed time, seed, source/config/data/spec hash, top 20 result và parameter export riêng.
3. Chọn parameter theo median validation score đa seed, không theo best single epoch.
4. Stability check: perturb mỗi parameter ±10% hoặc một discrete step; candidate phải không sụp PF/DD.
5. Không chạy lại seed chỉ vì kết quả xấu. Không dùng full period/holdout để chọn parameter.

Acceptance: parameter winner có bằng chứng train/validation đa seed và sensitivity; nếu các seed chọn vùng hoàn toàn khác nhau hoặc validation fail, loại candidate.

## 13. Phase 11 — bias, recursion, chi phí và pair concentration

Chỉ cho winner Phase 10:

1. `lookahead-analysis` trên full range và recent range, đủ minimum/targeted trades để từng enter/exit signal active được trigger. Report coverage theo signal/tag; signal không trigger là `UNVALIDATED`, không phải pass.
2. `recursive-analysis` với startup candle counts hợp lệ, kiểm tra từng indicator dùng cho signal/stop/sizing. Ghi variance và threshold chấp nhận trước.
3. Download bổ sung 5m futures data đúng 5 pair và exact range nếu cần; kiểm tra list-data. Chạy `--timeframe-detail 5m` để đánh giá intrabar exit/position adjustment.
4. Effective-cost stress tổng round-trip 0.1%, 0.2%, 0.4%, 0.6%; ghi cách ánh xạ fee+slippage/funding để không double count. Gate dùng mức 0.4%.
5. Leave-one-pair-out cho 5 pair, pair/side/tag contribution, exposure overlap và top-pair concentration.
6. Backtest có/không protections chỉ để đo impact; verdict bắt buộc dùng protections.

Artifact: `BIAS.md`, `RECURSIVE.md`, `COST_STRESS.md`, `PAIR_ROBUSTNESS.md` cùng raw outputs không overwrite.

Acceptance: tất cả tín hiệu active có coverage, không lookahead bias, recursive ổn, cost/pair gate qua. Fail bất kỳ mục nào thì không chạy Phase 12 tốn thời gian.

## 14. Phase 12 — Walk-Forward đầy đủ và block Monte Carlo

1. Chạy 6 folds theo spec, 300 epochs/fold, seed cố định, protections bật; dự kiến 2–5 giờ. Resume chỉ khi manifest/hash khớp hoàn toàn.
2. Validate parameter isolation: fold N không đọc artifact fold sau hoặc global hyperopt result.
3. Tổng hợp chronological OOS daily equity, fold table, side/pair/tag và confidence interval bootstrap block.
4. Nếu Walk-Forward qua Gate Q, chạy block Monte Carlo 10,000 paths với seed khóa, block 7 ngày và sensitivity 3/14/28.
5. Không rerun với seed khác để né tail xấu. Nếu dữ liệu OOS không đủ 200 trades, verdict `INSUFFICIENT OOS EVIDENCE`.

Acceptance: mọi tiêu chí Walk-Forward/Monte Carlo trong Gate Q qua; raw artifact, manifest, hashes và exact commands tồn tại.

## 15. Phase 13 — dry-run readiness, reconciliation và observability

Không khởi động/stop bot. Chỉ xây và test offline:

1. `healthcheck` phát hiện process cũ/code hash mismatch, stale market snapshot, stale data, DB lock, disk thấp, risk halt, clock skew và config secret thiếu.
2. Viết `tools/reconcile_dryrun.py` read-only: so sánh signal kỳ vọng theo closed candle với orders/trades DB, phân loại blocked-by-guard, rejected, missed, duplicate, delayed. Dùng DB copy/fixture trong tests.
3. Alert rules: process down, no candle, exchange error burst, snapshot stale, repeated deny, daily/weekly halt, drawdown threshold, open position orphan, code/config drift. Mock transport, rate-limit và deduplicate.
4. Runbook restart an toàn nêu rõ code không hot reload, kiểm tra open trades, backup DB, healthcheck và rollback; task này không thực thi runbook.
5. Đề xuất soak 30 ngày với acceptance: uptime, zero duplicate, reconciliation mismatch threshold, guard-denial distribution, realized slippage/funding, PF/DD chỉ mang tính quan sát. Không gọi `READY LIVE` từ backtest.

Acceptance: tests offline pass; healthcheck nhận diện được process hiện tại là stale so với source hash; có dry-run checklist người dùng review.

## 16. Phase 14 — tài liệu, final verification và verdict

1. Đồng bộ `README.md`, `HUONG_DAN_SU_DUNG.md`, `.env.example`, `DECISIONS.md` với code/config thực tế: strategy active, stop mechanism, overlay order, protections, paths, healthcheck và limitations.
2. Tạo `reports/pro_hardening/FINAL.md` gồm:
   - executive summary;
   - lỗi đã sửa và test chứng minh;
   - baseline/candidate/full/recent/WF/cost/MC tables đúng unit;
   - artifact index với hash;
   - Gate R/S/Q/O pass/fail từng dòng;
   - known risks, process cũ, data limitations;
   - một verdict duy nhất.
3. Chạy cuối: pytest, ruff, compileall, dependency check, CI-equivalent, config compose, list-strategies, report regression và healthcheck read-only.
4. Kiểm tra không secret, DB, WAL, log lớn, data hoặc artifact tạm bị đưa vào danh sách file cần commit.
5. `git status --short` và source manifest cuối; vì repo chưa có commit, liệt kê chính xác file đã chạm trong task dựa trên manifest/PROGRESS.

Verdict hợp lệ:

- `READY FOR DRY-RUN REVIEW`: chỉ khi Gate R, S, Q, O đều pass.
- `RESEARCH ONLY`: nền tảng tốt nhưng candidate chưa đủ robustness hoặc dry-run tooling chưa đủ.
- `NO ROBUST CANDIDATE`: hardening hoàn tất nhưng không candidate nào qua Q.
- `BLOCKED BY MEASUREMENT`: chỉ khi không thể sửa độ tin cậy metric; ghi blocker tái lập được.

Final response của Sonnet phải ngắn: verdict; file chính đã sửa; test counts; baseline/winner metrics; Gate table; link `FINAL.md`; cảnh báo bot cũ vẫn chạy nếu còn process. Không hỏi bước tiếp theo và không tự chạy bot.

## 17. Thứ tự ưu tiên nếu tài nguyên hoặc thời gian bị giới hạn

Không được bỏ Phase 0–9 và 16. Phase 10–12 chỉ chạy khi gate trước đó cho phép. Nếu candidate fail sớm, dùng thời gian còn lại để làm sâu test safety/config/healthcheck/reconciliation, không tạo candidate vô hạn.

Ước lượng:

| Nhóm | Thời gian |
|---|---:|
| Phase 0–4: measurement/report/WF/MC tooling | 1.5–3 giờ |
| Phase 5–7: execution/risk/config/CI | 2–4 giờ |
| Phase 8–9: candidate/spec/screening | 1–2 giờ |
| Phase 10: Hyperopt đa seed | 2–4 giờ |
| Phase 11: validation chi tiết | 1–2 giờ |
| Phase 12: full WF + MC | 2–5 giờ |
| Phase 13–16: operations/docs/final | 1–2 giờ |

## 18. Tài liệu chuẩn

- Configuration/env/overlay: <https://www.freqtrade.io/en/stable/configuration/>
- Strategy callbacks: <https://www.freqtrade.io/en/stable/strategy-callbacks/>
- Protections: <https://www.freqtrade.io/en/stable/plugins/>
- Hyperopt/MultiMetric: <https://www.freqtrade.io/en/stable/hyperopt/>
- Lookahead analysis: <https://www.freqtrade.io/en/stable/lookahead-analysis/>
- Recursive analysis: <https://www.freqtrade.io/en/stable/recursive-analysis/>
- Exchange notes/Hyperliquid: <https://www.freqtrade.io/en/stable/exchanges/>
- Advanced setup/database/logging: <https://docs.freqtrade.io/en/stable/advanced-setup/>

Ưu tiên local `rtk .venv\Scripts\freqtrade.exe <subcommand> -h` cho version đang cài. Nếu local CLI khác tài liệu, ghi version và chọn cú pháp local; không đoán option.
