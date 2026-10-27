# app/services/strategy/factory.py
"""Turns the strategies of a saved configuration into evaluate functions, ready for the engine."""
from app.services.strategy import custom
from app.services.strategy.ensemble import DEFAULT_THRESHOLD, EnsembleStrategy
from app.services.strategy.strategies import bollinger, momentum, rsi, sma

BUILT_IN = {
    "SMA": sma.evaluate,
    "RSI": rsi.evaluate,
    "BOLLINGER": bollinger.evaluate,
    "MOMENTUM": momentum.evaluate,
}

CUSTOM_PREFIX = "CUSTOM:"


def custom_label(name: str) -> str:
    """How a custom strategy appears in a configuration's list of strategies."""
    return f"{CUSTOM_PREFIX}{name}"


def build_components(strategy_names: list[str], custom_snapshots: list[dict] | None) -> tuple[dict, dict]:
    """Returns ({strategy name: evaluate function}, {strategy name: base strategy}).

    Custom strategies are rebuilt from the snapshot saved with the configuration, so a simulation can be
    reproduced even if the student later edits or deletes the strategy.
    """
    snapshots = {custom_label(c["name"]): c for c in (custom_snapshots or [])}
    components, bases = {}, {}
    for name in strategy_names:
        if name in BUILT_IN:
            components[name], bases[name] = BUILT_IN[name], name
        elif name in snapshots:
            snapshot = snapshots[name]
            components[name] = custom.build_evaluate(snapshot["base_strategy"], snapshot["params"])
            bases[name] = snapshot["base_strategy"]
        else:
            raise KeyError(f"Strategy {name} is not available")
    return components, bases


def build_strategy(strategy_names: list[str], custom_snapshots: list[dict] | None, regimes: dict | None,
                   threshold: float | None):
    """Returns (functions for the engine, threshold for the engine, ensemble or None).

    One strategy: it runs alone, exactly as before. Two or more: they are blended by an EnsembleStrategy.
    """
    components, bases = build_components(strategy_names, custom_snapshots)
    if len(components) == 1:
        return list(components.values()), None, None
    ensemble = EnsembleStrategy(components, regimes, threshold or DEFAULT_THRESHOLD, weight_keys=bases)
    return [ensemble.evaluate], ensemble.threshold, ensemble
