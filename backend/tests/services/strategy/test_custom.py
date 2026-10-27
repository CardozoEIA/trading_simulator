import pytest

from app.services.strategy import custom
from app.services.strategy.custom import InvalidStrategy, build_evaluate, validate_name, validate_parameters
from app.services.strategy.factory import BUILT_IN, build_components, build_strategy, custom_label
from app.services.strategy.strategies import bollinger, momentum, rsi, sma
from tests.services.regime.test_classifier import make_candles


@pytest.fixture(scope="module")
def candles():
    return make_candles([(250, 0.0007, 0.012), (150, -0.001, 0.02), (200, 0.0004, 0.009)], seed=8)


def signals_of(function, candles):
    return [(s.direction, s.score, s.reasoning) for s in (function(candles, i) for i in range(len(candles)))]


# ---- a custom strategy with the default parameters IS the built-in strategy ------------------------------

@pytest.mark.parametrize("base,module", [("SMA", sma), ("RSI", rsi), ("BOLLINGER", bollinger), ("MOMENTUM", momentum)])
def test_default_parameters_reproduce_the_built_in_strategy(candles, base, module):
    mine = build_evaluate(base, custom.default_parameters(base))
    assert signals_of(mine, candles) == signals_of(module.evaluate, candles)


def test_changing_a_parameter_changes_the_decisions(candles):
    fast = build_evaluate("SMA", {"short_period": 3, "long_period": 10})
    slow = build_evaluate("SMA", {"short_period": 20, "long_period": 100})
    assert signals_of(fast, candles) != signals_of(slow, candles)

    strict = build_evaluate("RSI", {"oversold": 15, "overbought": 85})
    default = build_evaluate("RSI", {})
    buys = lambda f: sum(1 for d, *_ in signals_of(f, candles) if d.value == "BUY")
    assert buys(strict) < buys(default)


def test_missing_parameters_use_the_defaults():
    assert validate_parameters("RSI", {"period": 10}) == {"period": 10, "oversold": 30, "overbought": 70}
    assert validate_parameters("MOMENTUM", None) == custom.default_parameters("MOMENTUM")


# ---- validation ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("base,params,message", [
    ("SMA", {"short_period": 20, "long_period": 10}, "shorter than the long"),
    ("SMA", {"short_period": 10, "long_period": 10}, "shorter than the long"),
    ("RSI", {"oversold": 60, "overbought": 55}, "Oversold limit must be between"),
    ("RSI", {"oversold": 45, "overbought": 51, "period": 14}, None),  # valid: 45 < 51
    ("RSI", {"period": 1}, "between 2 and 100"),
    ("BOLLINGER", {"num_std": 0}, "between 0.5 and 4"),
    ("BOLLINGER", {"period": 3}, "between 5 and 200"),
    ("MOMENTUM", {"threshold": 0.5}, "between 0.001 and 0.2"),
    ("SMA", {"short_period": 2.5}, "whole number"),
    ("SMA", {"short_period": "5"}, "must be a number"),
    ("SMA", {"short_period": True}, "must be a number"),
    ("SMA", {"fast": 3}, "not a parameter of SMA"),
    ("MACD", {}, "Unknown base strategy"),
])
def test_incompatible_configurations_are_rejected(base, params, message):
    if message is None:
        assert validate_parameters(base, params)
        return
    with pytest.raises(InvalidStrategy) as error:
        validate_parameters(base, params)
    assert any(message in problem for problem in error.value.problems)


def test_every_problem_is_reported_at_once():
    with pytest.raises(InvalidStrategy) as error:
        validate_parameters("RSI", {"period": 0, "oversold": 80, "overbought": 20})
    assert len(error.value.problems) == 3


def test_names():
    assert validate_name("  My   fast SMA ") == "My fast SMA"
    for bad in ("", "  ", "ab", "x" * 41, None, 5):
        with pytest.raises(InvalidStrategy):
            validate_name(bad)


def test_the_catalog_describes_every_parameter_with_limits():
    catalog = custom.parameter_catalog()
    assert set(catalog) == {"SMA", "RSI", "BOLLINGER", "MOMENTUM"}
    for items in catalog.values():
        for item in items:
            assert item["min"] <= item["default"] <= item["max"]
            assert item["label"] and item["description"]


# ---- integration with the engine -----------------------------------------------------------------------

def snapshot(name="Fast SMA", base="SMA", **params):
    return {"id": "11111111-1111-1111-1111-111111111111", "name": name, "base_strategy": base,
            "params": custom.validate_parameters(base, params)}


def test_components_come_from_built_ins_and_snapshots():
    components, bases = build_components(["RSI", custom_label("Fast SMA")], [snapshot(short_period=3, long_period=8)])
    assert list(components) == ["RSI", "CUSTOM:Fast SMA"]
    assert bases == {"RSI": "RSI", "CUSTOM:Fast SMA": "SMA"}


def test_an_unknown_strategy_is_an_error():
    with pytest.raises(KeyError):
        build_components(["CUSTOM:Gone"], [])


def test_one_strategy_runs_alone_and_several_are_blended(candles):
    functions, threshold, ensemble = build_strategy(["RSI"], None, {}, None)
    assert functions == [BUILT_IN["RSI"]] and threshold is None and ensemble is None

    functions, threshold, ensemble = build_strategy(["RSI", custom_label("Fast SMA")], [snapshot()], {}, 0.2)
    assert len(functions) == 1 and threshold == 0.2 and ensemble is not None
    assert ensemble.weight_keys["CUSTOM:Fast SMA"] == "SMA"


def test_a_custom_strategy_alone_matches_its_parameterised_built_in(candles):
    functions, _, _ = build_strategy([custom_label("Fast SMA")], [snapshot(short_period=3, long_period=8)], {}, None)
    expected = sma.build_evaluate(3, 8)
    assert signals_of(functions[0], candles) == signals_of(expected, candles)
