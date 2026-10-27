import inspect
import random
from datetime import date, timedelta

from app.services.historical_data.schema import Candle
from app.services.regime.classifier import (
    CHECKPOINT_EVERY,
    FIRST_CHECKPOINT_INDEX,
    MODEL_VERSION,
    Regime,
    build_regime_labels,
    checkpoint_indexes,
    train_model,
)
from app.services.strategy.strategies import bollinger, momentum, rsi, sma


def make_candles(segments, seed=1, start=date(2000, 1, 3), price=100.0):
    """segments: list of (days, daily_drift, daily_volatility)."""
    rng = random.Random(seed)
    candles, day = [], start
    for days, drift, vol in segments:
        for _ in range(days):
            price *= 1 + rng.gauss(drift, vol)
            candles.append(Candle(date=day, open=price, high=price, low=price, close=price, volume=1))
            day += timedelta(days=1)
    return candles


# 2 years of mixed "normal" history the model learns from.
NORMAL_HISTORY = [(125, 0.0007, 0.006), (125, 0.0, 0.007), (125, 0.0008, 0.006), (125, 0.0, 0.007)]


def labels_by_date(labels):
    return {label.date: label for label in labels}


def test_needs_enough_history_before_the_first_label():
    short = make_candles([(FIRST_CHECKPOINT_INDEX, 0.0, 0.01)])
    assert build_regime_labels(short) == []


def test_first_label_appears_at_the_first_checkpoint():
    candles = make_candles([(FIRST_CHECKPOINT_INDEX + 10, 0.0, 0.01)])
    labels = build_regime_labels(candles)
    assert len(labels) == 10
    assert labels[0].date == candles[FIRST_CHECKPOINT_INDEX].date


def test_crash_like_2008_is_high_volatility():
    # calm years, then a long violent fall (about 65% annualised volatility)
    candles = make_candles(NORMAL_HISTORY + [(90, -0.004, 0.04)] + [(60, 0.0, 0.006)])
    labels = labels_by_date(build_regime_labels(candles))
    crash = [labels[c.date] for c in candles[500 + 25 : 500 + 90]]
    share = sum(1 for label in crash if label.regime == Regime.HIGH_VOLATILITY) / len(crash)
    assert share >= 0.8


def test_covid_style_drop_and_rebound_is_high_volatility_then_calm():
    candles = make_candles(NORMAL_HISTORY + [(25, -0.012, 0.035), (40, 0.008, 0.03), (120, 0.0006, 0.006)], seed=3)
    labels = labels_by_date(build_regime_labels(candles))
    shock = [labels[c.date].regime for c in candles[500 + 22 : 500 + 65]]
    assert shock.count(Regime.HIGH_VOLATILITY) / len(shock) >= 0.8
    calm = [labels[c.date].regime for c in candles[-40:]]
    assert calm.count(Regime.HIGH_VOLATILITY) == 0


def test_steady_climb_is_trending_and_sideways_noise_is_range_bound():
    candles = make_candles(NORMAL_HISTORY + [(120, 0.003, 0.004), (120, 0.0, 0.0065)], seed=5)
    labels = labels_by_date(build_regime_labels(candles))
    climb = [labels[c.date].regime for c in candles[500 + 40 : 500 + 120]]
    sideways = [labels[c.date].regime for c in candles[500 + 160 : 500 + 240]]
    assert climb.count(Regime.TRENDING) / len(climb) >= 0.7
    # thresholds are percentiles of the past, so some noisy days always look like a trend: compare, don't demand purity
    sideways_range = sideways.count(Regime.RANGE_BOUND) / len(sideways)
    climb_range = climb.count(Regime.RANGE_BOUND) / len(climb)
    assert sideways_range >= 0.4
    assert sideways_range > climb_range + 0.3


def test_labels_are_reproducible():
    candles = make_candles(NORMAL_HISTORY, seed=9)
    assert build_regime_labels(candles) == build_regime_labels(candles)


# ---- no look-ahead -------------------------------------------------------------------------------------

def test_a_label_never_depends_on_later_candles():
    candles = make_candles(NORMAL_HISTORY + [(100, 0.0, 0.01)], seed=11)
    original = build_regime_labels(candles)

    cut = 560
    tampered = list(candles)
    for i in range(cut, len(tampered)):  # rewrite the whole future with a wild crash
        price = 10.0 + (i % 7) * 50
        tampered[i] = Candle(date=candles[i].date, open=price, high=price, low=price, close=price, volume=1)
    changed = labels_by_date(build_regime_labels(tampered))

    for label in original:
        if label.date < candles[cut].date:
            assert changed[label.date] == label


def test_cutting_the_series_does_not_change_earlier_labels():
    candles = make_candles(NORMAL_HISTORY + [(100, -0.002, 0.02)], seed=13)
    full = labels_by_date(build_regime_labels(candles))
    cut = len(candles) - 80
    partial = build_regime_labels(candles[:cut])
    assert partial
    for label in partial:
        assert full[label.date] == label


def test_every_model_is_trained_only_on_days_before_its_checkpoint():
    candles = make_candles(NORMAL_HISTORY, seed=15)
    for start in checkpoint_indexes(len(candles)):
        model = train_model(candles, start)
        assert model.trained_until < candles[start].date
        assert model.trained_until == candles[start - 1].date


def test_label_versions_record_the_checkpoint_in_force():
    candles = make_candles(NORMAL_HISTORY, seed=17)
    labels = build_regime_labels(candles)
    checkpoints = {label.checkpoint_date for label in labels}
    assert len(checkpoints) == len(checkpoint_indexes(len(candles)))
    for label in labels:
        assert label.checkpoint_date <= label.date
        assert label.model_version == f"{MODEL_VERSION}@{label.checkpoint_date.isoformat()}"
    # fixed schedule: the model changes exactly every CHECKPOINT_EVERY days
    first_block = [label for label in labels if label.checkpoint_date == labels[0].checkpoint_date]
    assert len(first_block) == CHECKPOINT_EVERY


def test_regime_is_never_an_input_of_a_strategy():
    for module in (sma, rsi, bollinger, momentum):
        assert list(inspect.signature(module.evaluate).parameters) == ["candles", "current_index"]
