# app/services/strategy/custom.py
"""US-21: custom strategies = one of the four known strategies with parameters chosen by the student.

A custom strategy is NOT free-form code: it is a base type plus validated numbers, so it is safe to run
and the backtesting engine treats it like any other strategy (same evaluate(candles, index) interface).
"""
from dataclasses import dataclass

from app.services.strategy.strategies import bollinger, momentum, rsi, sma

NAME_MIN_LENGTH = 3
NAME_MAX_LENGTH = 40
MAX_CUSTOM_STRATEGIES = 20


@dataclass(frozen=True)
class ParamSpec:
    name: str
    label: str
    description: str
    kind: str  # "int" | "float"
    default: float
    minimum: float
    maximum: float


PARAMETERS: dict[str, list[ParamSpec]] = {
    "SMA": [
        ParamSpec("short_period", "Short average (days)", "Days of the fast moving average.", "int", 5, 2, 100),
        ParamSpec("long_period", "Long average (days)", "Days of the slow moving average. Must be longer than the short one.", "int", 20, 3, 400),
    ],
    "RSI": [
        ParamSpec("period", "RSI period (days)", "Days used to measure recent strength.", "int", 14, 2, 100),
        ParamSpec("oversold", "Oversold limit", "Below this RSI the strategy sees a buying opportunity.", "float", 30, 1, 49),
        ParamSpec("overbought", "Overbought limit", "Above this RSI the strategy sees a selling opportunity. Must be higher than the oversold limit.", "float", 70, 51, 99),
    ],
    "BOLLINGER": [
        ParamSpec("period", "Band period (days)", "Days of the moving average the bands are built around.", "int", 20, 5, 200),
        ParamSpec("num_std", "Band width (std. deviations)", "How far from the average the bands sit.", "float", 2, 0.5, 4),
    ],
    "MOMENTUM": [
        ParamSpec("period", "Look-back (days)", "Days back the current price is compared with.", "int", 10, 2, 200),
        ParamSpec("threshold", "Minimum move", "Price change (0.02 = 2%) needed to trigger a signal.", "float", 0.02, 0.001, 0.2),
    ],
}

BUILDERS = {
    "SMA": sma.build_evaluate,
    "RSI": rsi.build_evaluate,
    "BOLLINGER": bollinger.build_evaluate,
    "MOMENTUM": momentum.build_evaluate,
}


class InvalidStrategy(ValueError):
    """Raised with every problem found, so the student can fix them all at once."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def default_parameters(base: str) -> dict:
    return {spec.name: spec.default for spec in PARAMETERS[base]}


def validate_name(name) -> str:
    if not isinstance(name, str) or not name.strip():
        raise InvalidStrategy(["The strategy needs a name"])
    clean = " ".join(name.split())
    if not NAME_MIN_LENGTH <= len(clean) <= NAME_MAX_LENGTH:
        raise InvalidStrategy([f"The name must have between {NAME_MIN_LENGTH} and {NAME_MAX_LENGTH} characters"])
    return clean


def validate_parameters(base: str, params: dict | None) -> dict:
    """Returns the parameters with defaults filled in and numbers converted. Raises InvalidStrategy."""
    if base not in PARAMETERS:
        raise InvalidStrategy([f"Unknown base strategy '{base}'. Choose one of: {', '.join(PARAMETERS)}"])
    params = dict(params or {})
    specs = {spec.name: spec for spec in PARAMETERS[base]}
    problems = [f"'{key}' is not a parameter of {base}" for key in params if key not in specs]

    values: dict = {}
    for name, spec in specs.items():
        raw = params.get(name, spec.default)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            problems.append(f"{spec.label} must be a number")
            continue
        if spec.kind == "int" and raw != int(raw):
            problems.append(f"{spec.label} must be a whole number")
            continue
        value = int(raw) if spec.kind == "int" else float(raw)
        if not spec.minimum <= value <= spec.maximum:
            problems.append(f"{spec.label} must be between {spec.minimum:g} and {spec.maximum:g}")
            continue
        values[name] = value

    if not problems:  # rules that involve several parameters
        if base == "SMA" and values["short_period"] >= values["long_period"]:
            problems.append("The short average must be shorter than the long average")
        if base == "RSI" and values["oversold"] >= values["overbought"]:
            problems.append("The oversold limit must be lower than the overbought limit")
    if problems:
        raise InvalidStrategy(problems)
    return values


def build_evaluate(base: str, params: dict | None):
    """The evaluate(candles, index) function of a custom strategy. Validates first."""
    return BUILDERS[base](**validate_parameters(base, params))


def describe(base: str, params: dict) -> str:
    """One line for lists: 'Custom RSI: period 14, oversold 30, overbought 70'."""
    labels = {spec.name: spec.label.split(" (")[0].lower() for spec in PARAMETERS[base]}
    values = ", ".join(f"{labels.get(key, key)} {value:g}" for key, value in params.items())
    return f"Custom {base} strategy: {values}"


def parameter_catalog() -> dict:
    """What the editor needs to draw the form: parameters, defaults and limits of each base strategy."""
    return {
        base: [
            {"name": s.name, "label": s.label, "description": s.description, "kind": s.kind,
             "default": s.default, "min": s.minimum, "max": s.maximum}
            for s in specs
        ]
        for base, specs in PARAMETERS.items()
    }
