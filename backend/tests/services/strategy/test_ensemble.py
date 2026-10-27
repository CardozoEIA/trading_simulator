import pytest

from app.services.regime.classifier import Regime
from app.services.strategy import ensemble as ens
from app.services.strategy.engine import run_strategy
from app.services.strategy.ensemble import EnsembleStrategy, UNKNOWN, WEIGHT_TABLE, blend, weights_for
from app.services.strategy.schema import DecisionAction, StrategySignal
from app.services.strategy.strategies import bollinger, momentum, rsi, sma
from tests.services.regime.test_classifier import make_candles

BUILT_IN = {"SMA": sma.evaluate, "RSI": rsi.evaluate, "BOLLINGER": bollinger.evaluate, "MOMENTUM": momentum.evaluate}


def signal(score):
    direction = DecisionAction.BUY if score > 0 else DecisionAction.SELL if score < 0 else DecisionAction.HOLD
    return StrategySignal(direction=direction, score=score, reasoning=f"score {score}")


@pytest.fixture(scope="module")
def candles():
    return make_candles([(200, 0.0008, 0.01), (150, -0.001, 0.015), (200, 0.0005, 0.008)], seed=4)


# ---- weight table --------------------------------------------------------------------------------------

def test_every_regime_row_adds_up_to_one_and_has_a_rationale():
    for regime, row in WEIGHT_TABLE.items():
        assert sum(row.values()) == pytest.approx(1.0), regime
        assert set(row) == {"SMA", "RSI", "BOLLINGER", "MOMENTUM"}
        assert regime in ens.WEIGHT_RATIONALE and len(ens.WEIGHT_RATIONALE[regime]) > 40


def test_the_table_covers_every_regime_the_classifier_can_produce():
    assert {r.value for r in Regime} | {UNKNOWN} == set(WEIGHT_TABLE)


def test_trend_followers_dominate_in_trends_and_reversal_strategies_in_ranges():
    trending, ranging = WEIGHT_TABLE["TRENDING"], WEIGHT_TABLE["RANGE_BOUND"]
    assert trending["SMA"] > trending["RSI"] and trending["MOMENTUM"] > trending["BOLLINGER"]
    assert ranging["RSI"] > ranging["SMA"] and ranging["BOLLINGER"] > ranging["MOMENTUM"]


def test_weights_are_rescaled_to_the_selected_strategies():
    weights = weights_for("TRENDING", ["SMA", "RSI"])
    assert sum(weights.values()) == pytest.approx(1.0)
    assert weights["SMA"] == pytest.approx(0.35 / 0.50)
    assert weights_for("TRENDING", ["RSI"]) == {"RSI": 1.0}


def test_unknown_or_missing_regime_uses_equal_weights():
    assert weights_for(None, ["SMA", "RSI"]) == weights_for(UNKNOWN, ["SMA", "RSI"]) == {"SMA": 0.5, "RSI": 0.5}


# ---- blending ------------------------------------------------------------------------------------------

def test_blended_score_is_the_weighted_sum():
    score, weights = blend({"SMA": signal(1.0), "RSI": signal(-1.0)}, "TRENDING")
    assert weights["SMA"] == pytest.approx(0.7) and weights["RSI"] == pytest.approx(0.3)
    assert score == pytest.approx(0.7 - 0.3)


def test_the_same_signals_blend_differently_in_different_regimes():
    signals = {"SMA": signal(1.0), "RSI": signal(-1.0)}
    trending, _ = blend(signals, "TRENDING")
    ranging, _ = blend(signals, "RANGE_BOUND")
    assert trending > 0 > ranging


def test_threshold_turns_the_score_into_buy_sell_hold():
    assert ens.decide(0.3, 0.25) == DecisionAction.BUY
    assert ens.decide(-0.3, 0.25) == DecisionAction.SELL
    assert ens.decide(0.25, 0.25) == DecisionAction.HOLD  # the limit itself is neutral
    assert ens.decide(0.3, 0.5) == DecisionAction.HOLD


def test_invalid_configuration_is_rejected():
    with pytest.raises(ValueError):
        EnsembleStrategy({})
    with pytest.raises(ValueError):
        EnsembleStrategy({"SMA": sma.evaluate}, threshold=0)


# ---- regression guarantee and reproducibility ------------------------------------------------------------

@pytest.mark.parametrize("name", list(BUILT_IN))
def test_an_ensemble_with_one_strategy_decides_exactly_like_that_strategy(candles, name):
    alone = run_strategy(candles, [BUILT_IN[name]])
    regimes = {c.date: Regime.TRENDING for c in candles[::2]}  # whatever the regime, one strategy weighs 1.0
    combined = run_strategy(candles, [EnsembleStrategy({name: BUILT_IN[name]}, regimes).evaluate])
    assert [(d.date, d.action) for d in combined] == [(d.date, d.action) for d in alone]


def test_the_ensemble_signal_of_one_strategy_has_the_same_score(candles):
    strategy = EnsembleStrategy({"RSI": rsi.evaluate})
    for i in range(0, len(candles), 17):
        assert strategy.evaluate(candles, i).score == pytest.approx(rsi.evaluate(candles, i).score)


def test_same_configuration_gives_the_same_results(candles):
    regimes = {c.date: Regime.RANGE_BOUND if i % 3 else Regime.TRENDING for i, c in enumerate(candles)}

    def run():
        strategy = EnsembleStrategy(BUILT_IN, regimes)
        return run_strategy(candles, [strategy.evaluate]), strategy.breakdowns

    first, second = run(), run()
    assert first[0] == second[0]
    assert first[1] == second[1]


def test_a_custom_threshold_changes_when_the_engine_acts(candles):
    loose = EnsembleStrategy(BUILT_IN, threshold=0.05)
    strict = EnsembleStrategy(BUILT_IN, threshold=0.4)
    loose_actions = [d for d in run_strategy(candles, [loose.evaluate], threshold=0.05) if d.action != DecisionAction.HOLD]
    strict_actions = [d for d in run_strategy(candles, [strict.evaluate], threshold=0.4) if d.action != DecisionAction.HOLD]
    assert len(loose_actions) > len(strict_actions)


# ---- breakdown -----------------------------------------------------------------------------------------

def test_every_day_keeps_the_full_breakdown(candles):
    regimes = {c.date: Regime.TRENDING for c in candles}
    strategy = EnsembleStrategy(BUILT_IN, regimes, threshold=0.1)
    run_strategy(candles, [strategy.evaluate])

    assert len(strategy.breakdowns) == len(candles)
    day = candles[100].date
    item = strategy.breakdowns[day]
    assert item["regime"] == "TRENDING" and item["threshold"] == 0.1
    assert {c["strategy"] for c in item["components"]} == set(BUILT_IN)
    assert sum(c["weight"] for c in item["components"]) == pytest.approx(1.0)
    assert item["blended_score"] == pytest.approx(sum(c["weight"] * c["score"] for c in item["components"]), abs=1e-5)
    for component in item["components"]:
        assert component["reasoning"]


def test_days_without_a_label_are_reported_as_unknown(candles):
    strategy = EnsembleStrategy(BUILT_IN, {})
    strategy.evaluate(candles, 50)
    assert strategy.breakdowns[candles[50].date]["regime"] == UNKNOWN


def test_regime_labels_and_plain_strings_are_both_accepted(candles):
    from tests.modules.regime.test_service import label

    by_label = EnsembleStrategy(BUILT_IN, {candles[60].date: label(candles[60].date, Regime.RANGE_BOUND)})
    by_text = EnsembleStrategy(BUILT_IN, {candles[60].date: "RANGE_BOUND"})
    assert by_label.evaluate(candles, 60).score == pytest.approx(by_text.evaluate(candles, 60).score)
