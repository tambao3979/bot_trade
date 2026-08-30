# Walk‑forward: TrendPullback

## Configuration
- timerange: 20260301-20260501
- folds: 1
- IS months: 1
- OOS months: 1

## Per‑fold results

| fold | IS start | IS end | OOS start | OOS end | trades | PF | max DD % | Sharpe |
|---|---|---|---|---|---|---|---|---|
| 1 | 20260301 | 20260401 | 20260401 | 20260501 | 20 | 0.28 | 7.16 | -0.47 |

## Aggregated OOS metrics

- total trades: 20
- profit factor: 0.277
- max drawdown: 7.16%
- Sharpe (per trade): -0.470
- total return (compounded): -7.12%
- expectancy (per trade): -0.0037

## Verdict: FAIL

- profit_factor ≥ 1.3: FAIL (0.277)
- max_drawdown ≤ 20%: PASS (7.16%)
- trade_count ≥ 200: FAIL (20)
- sharpe ≥ 1.0: FAIL (-0.470)
