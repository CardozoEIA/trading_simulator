# app/services/strategy/ensemble.py
"""US-24: combines several strategies into ONE weighted decision, adjusted by the market regime.

The combination is a fixed set of rules written by the team, not a learned model, so every weight can be
justified in plain language (see WEIGHT_TABLE below and docs/ensemble.md).

Blending formula, for one day:

    weights   = WEIGHT_TABLE[regime of that day]           (UNKNOWN table when there is no label)
    active    = the strategies the student selected
    w_i       = weights[strategy_i] / sum(weights[s] for s in active)      # re-scaled so they add up to 1
    blended   = sum(w_i * score_i)                                           # in [-1, +1]
    direction = BUY if blended > threshold, SELL if blended < -threshold, otherwise HOLD

With a single active strategy, w = 1 and blended = its own score, so the ensemble gives exactly the same
decisions as that strategy alone (regression guarantee).
"""
from datetime import date

from app.services.strategy.schema import DecisionAction, StrategySignal

UNKNOWN = "UNKNOWN"  # the day has no regime label (not enough earlier history, or labels unavailable)

DEFAULT_THRESHOLD = 0.1  # same zone limits the engine has always used: BUY above +0.1, SELL below -0.1

# One row per regime, one weight per strategy. Each row adds up to 1.0.
# Trend followers: SMA, MOMENTUM. Mean reversion: RSI, BOLLINGER.
WEIGHT_TABLE: dict[str, dict[str, float]] = {
    "TRENDING": {"SMA": 0.35, "MOMENTUM": 0.35, "RSI": 0.15, "BOLLINGER": 0.15},
    "RANGE_BOUND": {"SMA": 0.15, "MOMENTUM": 0.15, "RSI": 0.35, "BOLLINGER": 0.35},
    "HIGH_VOLATILITY": {"SMA": 0.25, "MOMENTUM": 0.25, "RSI": 0.25, "BOLLINGER": 0.25},
    UNKNOWN: {"SMA": 0.25, "MOMENTUM": 0.25, "RSI": 0.25, "BOLLINGER": 0.25},
}

WEIGHT_RATIONALE: dict[str, str] = {
    "TRENDING": (
        "When prices move steadily in one direction, the strategies that follow the trend (moving-average "
        "crossover and momentum) get 0.35 each; the ones that bet on a reversal (RSI, Bollinger) get only "
        "0.15 because they tend to sell too early in a rising market and buy too early in a falling one."
    ),
    "RANGE_BOUND": (
        "When prices wander without a clear direction, reversal strategies (RSI and Bollinger bands) get "
        "0.35 each, because the price tends to return to its average; trend followers get 0.15 because "
        "their crossovers fire on noise."
    ),
    "HIGH_VOLATILITY": (
        "When the market is turbulent no style has a proven edge, so all four weigh the same (0.25). "
        "Betting on one style in the most unpredictable periods would be a guess."
    ),
    UNKNOWN: (
        "Without a regime label the ensemble does not take sides: all strategies weigh the same (0.25). "
        "This is also the fallback when regime labels are unavailable."
    ),
}

# Fallback weight for a strategy that is not in the table.
DEFAULT_WEIGHT = 0.25


def weights_for(regime: str | None, strategy_names: list[str], weight_keys: dict | None = None) -> dict[str, float]:
    """Weights of the active strategies for a regime, re-scaled to add up to 1.

    `weight_keys` maps a strategy name to the table column it uses: a custom strategy (US-21) weighs like
    the built-in strategy it is based on."""
    row = WEIGHT_TABLE.get(regime or UNKNOWN, WEIGHT_TABLE[UNKNOWN])
    keys = weight_keys or {}
    raw = {name: row.get(keys.get(name, name), DEFAULT_WEIGHT) for name in strategy_names}
    total = sum(raw.values())
    return {name: value / total for name, value in raw.items()}


def blend(signals: dict[str, StrategySignal], regime: str | None, weight_keys: dict | None = None) -> tuple[float, dict[str, float]]:
    """Weighted sum of the scores. Returns (blended score, weights used)."""
    weights = weights_for(regime, list(signals), weight_keys)
    score = sum(weights[name] * signal.score for name, signal in signals.items())
    return score, weights


def decide(score: float, threshold: float) -> DecisionAction:
    if score > threshold:
        return DecisionAction.BUY
    if score < -threshold:
        return DecisionAction.SELL
    return DecisionAction.HOLD


class EnsembleStrategy:
    """Same interface as every strategy: evaluate(candles, current_index) -> StrategySignal.

    `components` maps a strategy name to its evaluate function. `regimes` maps a date to the regime label
    (US-23) or to its string value; missing dates use the UNKNOWN row.
    Every day evaluated keeps its full breakdown in `breakdowns`, ready to be stored (US-11) and explained (US-20).
    """

    def __init__(self, components: dict, regimes: dict | None = None, threshold: float = DEFAULT_THRESHOLD,
                 weight_keys: dict | None = None):
        if not components:
            raise ValueError("An ensemble needs at least one strategy")
        if threshold <= 0:
            raise ValueError("The threshold must be greater than 0")
        self.components = dict(components)
        self.regimes = regimes or {}
        self.threshold = threshold
        self.weight_keys = weight_keys or {}
        self.breakdowns: dict[date, dict] = {}

    def _regime_on(self, day: date) -> str | None:
        item = self.regimes.get(day)
        if item is None:
            return None
        regime = getattr(item, "regime", item)  # a RegimeLabel, a Regime or a plain string
        return getattr(regime, "value", regime)

    def evaluate(self, candles: list, current_index: int) -> StrategySignal:
        day = candles[current_index].date
        regime = self._regime_on(day)

        signals = {name: fn(candles, current_index) for name, fn in self.components.items()}
        score, weights = blend(signals, regime, self.weight_keys)
        direction = decide(score, self.threshold)

        self.breakdowns[day] = {
            "regime": regime or UNKNOWN,
            "threshold": self.threshold,
            "blended_score": round(score, 6),
            "decision": direction.value,
            "components": [
                {
                    "strategy": name,
                    "based_on": self.weight_keys.get(name, name),
                    "direction": signal.direction.value,
                    "score": round(signal.score, 6),
                    "weight": round(weights[name], 6),
                    "contribution": round(weights[name] * signal.score, 6),
                    "reasoning": signal.reasoning,
                }
                for name, signal in signals.items()
            ],
        }

        parts = ", ".join(f"{name} {signals[name].score:+.2f}x{weights[name]:.2f}" for name in signals)
        return StrategySignal(
            direction=direction,
            score=score,
            reasoning=f"Ensemble ({regime or UNKNOWN} weights): {parts} = {score:+.3f}",
        )

    def __call__(self, candles: list, current_index: int) -> StrategySignal:
        return self.evaluate(candles, current_index)
