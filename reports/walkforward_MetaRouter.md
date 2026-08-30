# Walk‑forward: MetaRouter

## Configuration
- timerange: 20260301-20260501
- folds: 1
- IS months: 1
- OOS months: 1

## Per‑fold results

| fold | IS start | IS end | OOS start | OOS end | trades | PF | max DD % | Sharpe |
|---|---|---|---|---|---|---|---|---|
| 1 | 20260301 | 20260401 | 20260401 | 20260501 | 41 | 0.25 | 12.31 | -0.49 |

## Aggregated OOS metrics

- total trades: 41
- profit factor: 0.251
- max drawdown: 12.31%
- Sharpe (per trade): -0.485
- total return (compounded): -12.16%
- expectancy (per trade): -0.0031

## Verdict: FAIL

- profit_factor ≥ 1.3: FAIL (0.251)
- max_drawdown ≤ 20%: PASS (12.31%)
- trade_count ≥ 200: FAIL (41)
- sharpe ≥ 1.0: FAIL (-0.485)
