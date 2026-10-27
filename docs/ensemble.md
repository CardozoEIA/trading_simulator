# Strategies, market regimes and the ensemble

How a simulation with several strategies decides, and where each number comes from.
Code: `backend/app/services/regime/classifier.py`, `backend/app/services/strategy/ensemble.py`,
`backend/app/services/strategy/custom.py`.

## 1. Market regime (US-23)

Every trading day gets one of three labels. The label is **context only**: a strategy never reads it to decide BUY/SELL/HOLD
(its `evaluate(candles, index)` has no regime argument). It is stored next to the technical signals
(`simulation_signals.regime`), the agent can read it (`get_market_regime`) and the ensemble uses it to pick weights.

| Regime | Rule (thresholds are learned, see below) |
|---|---|
| `HIGH_VOLATILITY` | annualised volatility of the last 20 days ≥ its threshold |
| `TRENDING` | otherwise, trend strength over the last 30 days ≥ its threshold |
| `RANGE_BOUND` | otherwise |

- **Volatility**: standard deviation of the last 20 daily returns × √252.
- **Trend strength** (Kaufman efficiency ratio): |price change over 30 days| ÷ sum of the absolute daily changes. 1 = a straight line, 0 = pure back-and-forth.
- **"Training"** = learning two thresholds: the 80th percentile of volatility and the 60th percentile of trend strength, both measured on the history *before* a checkpoint.
- **Walk-forward, no look-ahead**: the first label needs 282 days of history (30 warm-up + 252 to learn from). The thresholds are re-learned every 63 trading days (about a quarter) using only the days before that checkpoint. A label for date D is produced by the model of the latest checkpoint ≤ D and never depends on a candle after D (`tests/services/regime/test_classifier.py` rewrites the whole future and checks that earlier labels do not move).
- **Versioned**: `market_regimes` stores for every label the algorithm version (`wf-regime-v1`) and the checkpoint (`model_version = wf-regime-v1@<checkpoint date>`).
- **Precalculated offline**: `python -m scripts.precalculate_regimes [ASSET]`. If the table is empty a simulation recomputes the labels from the asset's history (same result, because the method is causal) and, if even that fails, runs without regimes (the ensemble then uses equal weights).

Limits to keep in mind: percentile thresholds mean some calm days always look like a trend; the labels describe the past of each day, they do not predict anything.

## 2. Ensemble (US-24)

With one strategy the simulation runs exactly as before. With two or more (built-in and/or custom), an `EnsembleStrategy` blends them. It implements the same `evaluate(candles, index) -> StrategySignal` interface, so the engine only gained an optional `threshold`.

For each day:

```
weights   = WEIGHT_TABLE[regime of the day]        (UNKNOWN row if the day has no label)
w_i       = weights[strategy_i] / Σ weights[active strategies]        # re-scaled to add up to 1
blended   = Σ w_i × score_i                                            # each score is in [-1, +1]
decision  = BUY if blended > threshold · SELL if blended < -threshold · HOLD otherwise
```

`threshold` defaults to 0.1 (the limit the engine always used) and can be set per configuration (`ensemble_threshold`, > 0 and ≤ 1). As before, the engine only emits a BUY/SELL when the blended signal *enters* that zone.

### Weight table (fixed rules written by the team, not learned)

| Regime | SMA | MOMENTUM | RSI | BOLLINGER |
|---|---|---|---|---|
| `TRENDING` | 0.35 | 0.35 | 0.15 | 0.15 |
| `RANGE_BOUND` | 0.15 | 0.15 | 0.35 | 0.35 |
| `HIGH_VOLATILITY` | 0.25 | 0.25 | 0.25 | 0.25 |
| `UNKNOWN` (no label) | 0.25 | 0.25 | 0.25 | 0.25 |

Why each row:

- **Trending**: trend followers (moving-average crossover, momentum) get 0.35 each; reversal strategies (RSI, Bollinger) get 0.15 because they tend to sell too early in a rising market and buy too early in a falling one.
- **Range-bound**: reversal strategies get 0.35 each, because the price tends to return to its average; trend followers get 0.15 because their crossovers fire on noise.
- **High volatility**: no style has a proven edge in turbulent markets, so all weigh the same. Betting on one style there would be a guess.
- **Unknown**: without a label the ensemble does not take sides. Also the fallback when regimes are unavailable.

A custom strategy (US-21) weighs like the built-in strategy it is based on. With only one active strategy its weight is 1, so **the ensemble gives exactly the same decisions as that strategy alone** (tested for each of the four).

### What is stored

Every decision of an ensemble run keeps its breakdown in `simulation_decisions.breakdown`:
`{regime, threshold, blended_score, decision, components: [{strategy, based_on, direction, score, weight, contribution, reasoning}]}`.
The agent reads it with `get_ensemble_breakdown(date)` to say which strategies voted, with what score and weight.

The runs are reproducible: same candles, same configuration, same labels give the same decisions (tested).

## 3. Custom strategies (US-21)

A custom strategy is one of the four known strategies with parameters chosen by the student, not free-form code:

| Base | Parameters (default, allowed range) |
|---|---|
| SMA | `short_period` (5, 2–100), `long_period` (20, 3–400); short < long |
| RSI | `period` (14, 2–100), `oversold` (30, 1–49), `overbought` (70, 51–99); oversold < overbought |
| BOLLINGER | `period` (20, 5–200), `num_std` (2, 0.5–4) |
| MOMENTUM | `period` (10, 2–200), `threshold` (0.02, 0.001–0.2) |

With the default values a custom strategy produces the same signals as the built-in one (tested). Names are 3–40 characters and unique per student; each student keeps up to 20. A configuration stores a **snapshot** of the custom strategies it uses, so editing or deleting a strategy later never changes a past simulation.

Endpoints: `GET/POST /custom-strategies`, `GET/PUT/DELETE /custom-strategies/{id}`, `POST /custom-strategies/validate`, `GET /custom-strategies/parameters` (limits for the editor). A configuration references them with `custom_strategy_ids` in `POST /backtest/configuration`.

## 4. Database changes

Run in the Supabase SQL editor, in order: `005_market_regimes.sql`, `006_custom_strategies_and_ensemble.sql`, `007_agent_traces.sql`, then `python -m scripts.precalculate_regimes`.
