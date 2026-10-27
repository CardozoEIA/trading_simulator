# app/services/regime/classifier.py
"""US-23: market-regime classification with a walk-forward schedule (no look-ahead).

The regime is CONTEXT only: it is stored next to the technical signals, shown to the agent and used by
the ensemble (US-24) to pick a weight table. A single strategy never reads it to decide BUY/SELL/HOLD.

How it works (kept simple on purpose, so every label can be explained in plain language):

1. Two features per day, both computed ONLY from that day and earlier candles:
   - volatility: annualised standard deviation of the last VOLATILITY_WINDOW daily returns.
   - trend strength: Kaufman efficiency ratio over TREND_WINDOW days = |net price change| / sum of the
     absolute daily changes. 1 = straight line, 0 = pure back-and-forth noise.
2. "Training" = learning two thresholds from the history that precedes a checkpoint:
   the VOLATILITY_PERCENTILE of volatility and the TREND_PERCENTILE of trend strength.
3. Labelling: volatility >= its threshold -> HIGH_VOLATILITY; else trend strength >= its threshold ->
   TRENDING; otherwise RANGE_BOUND.
4. Walk-forward: every CHECKPOINT_EVERY trading days the thresholds are re-learned using only the days
   BEFORE that checkpoint. Days of a block use the thresholds of the checkpoint that opens the block, so
   a label on date D never depends on any candle after D.
"""
import math
from dataclasses import dataclass
from datetime import date
from enum import Enum


class Regime(str, Enum):
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    TRENDING = "TRENDING"
    RANGE_BOUND = "RANGE_BOUND"


MODEL_VERSION = "wf-regime-v1"

VOLATILITY_WINDOW = 20
TREND_WINDOW = 30
TRADING_DAYS_PER_YEAR = 252

VOLATILITY_PERCENTILE = 80
TREND_PERCENTILE = 60

# One year of features is the minimum needed to learn the thresholds.
MIN_TRAINING_DAYS = 252
# Re-train roughly every quarter.
CHECKPOINT_EVERY = 63

WARMUP_DAYS = max(VOLATILITY_WINDOW, TREND_WINDOW)
FIRST_CHECKPOINT_INDEX = WARMUP_DAYS + MIN_TRAINING_DAYS


@dataclass(frozen=True)
class RegimeModel:
    volatility_threshold: float
    trend_threshold: float
    trained_until: date  # last date of the data used to learn the thresholds (always before the checkpoint)
    training_days: int


@dataclass(frozen=True)
class RegimeLabel:
    date: date
    regime: Regime
    volatility: float
    trend_strength: float
    checkpoint_date: date  # the checkpoint whose model produced this label
    model_version: str     # e.g. "wf-regime-v1@2019-01-02"


def volatility_at(closes: list[float], index: int) -> float | None:
    """Annualised volatility using only closes[index - VOLATILITY_WINDOW .. index]."""
    if index < VOLATILITY_WINDOW:
        return None
    window = closes[index - VOLATILITY_WINDOW : index + 1]
    returns = [window[i] / window[i - 1] - 1 for i in range(1, len(window))]
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(TRADING_DAYS_PER_YEAR)


def trend_strength_at(closes: list[float], index: int) -> float | None:
    """Efficiency ratio using only closes[index - TREND_WINDOW .. index]. In [0, 1]."""
    if index < TREND_WINDOW:
        return None
    window = closes[index - TREND_WINDOW : index + 1]
    path = sum(abs(window[i] - window[i - 1]) for i in range(1, len(window)))
    if path == 0:
        return 0.0
    return abs(window[-1] - window[0]) / path


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile / 100
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _features(closes: list[float]) -> list[tuple[float | None, float | None]]:
    return [(volatility_at(closes, i), trend_strength_at(closes, i)) for i in range(len(closes))]


def train_model(candles: list, end_index: int) -> RegimeModel:
    """Learns the thresholds from candles[:end_index] ONLY (end_index is exclusive)."""
    closes = [c.close for c in candles[:end_index]]
    volatilities, trends = [], []
    for volatility, trend in _features(closes):
        if volatility is not None and trend is not None:
            volatilities.append(volatility)
            trends.append(trend)
    if len(volatilities) < MIN_TRAINING_DAYS:
        raise ValueError(f"At least {MIN_TRAINING_DAYS} days of features are needed to train the model")
    return RegimeModel(
        volatility_threshold=_percentile(volatilities, VOLATILITY_PERCENTILE),
        trend_threshold=_percentile(trends, TREND_PERCENTILE),
        trained_until=candles[end_index - 1].date,
        training_days=len(volatilities),
    )


def classify(volatility: float, trend_strength: float, model: RegimeModel) -> Regime:
    if volatility >= model.volatility_threshold:
        return Regime.HIGH_VOLATILITY
    if trend_strength >= model.trend_threshold:
        return Regime.TRENDING
    return Regime.RANGE_BOUND


def checkpoint_indexes(total_candles: int) -> list[int]:
    return list(range(FIRST_CHECKPOINT_INDEX, total_candles, CHECKPOINT_EVERY))


def build_regime_labels(candles: list) -> list[RegimeLabel]:
    """Walk-forward labels for every day from the first checkpoint on.

    Earlier days get no label: there was not enough history to train a model without looking ahead.
    `candles` must be sorted by date. Deterministic: same candles -> same labels.
    """
    checkpoints = checkpoint_indexes(len(candles))
    if not checkpoints:
        return []

    closes = [c.close for c in candles]
    labels: list[RegimeLabel] = []

    for position, start in enumerate(checkpoints):
        end = checkpoints[position + 1] if position + 1 < len(checkpoints) else len(candles)
        model = train_model(candles, start)
        checkpoint_date = candles[start].date
        version = f"{MODEL_VERSION}@{checkpoint_date.isoformat()}"

        for index in range(start, end):
            volatility = volatility_at(closes, index)
            trend = trend_strength_at(closes, index)
            labels.append(RegimeLabel(
                date=candles[index].date,
                regime=classify(volatility, trend, model),
                volatility=volatility,
                trend_strength=trend,
                checkpoint_date=checkpoint_date,
                model_version=version,
            ))
    return labels
