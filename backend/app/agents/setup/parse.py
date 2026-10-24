# app/agents/setup/parse.py
"""Turns the model's extraction into configuration values (US-29). Pure Python.

The model only reads the description; every value is parsed and checked here. A value is
kept only when it is backed by the student's own words, so a field the student did not
mention is asked back instead of being filled with a guess.
"""
import re
from datetime import date, timedelta

from app.modules.backtest.schema import StrategyType
from app.modules.risk.service import MAX_PERCENTAGE, MIN_PERCENTAGE

FIELDS = (
    "asset", "start_date", "end_date", "initial_capital", "strategies",
    "stop_loss_percentage", "max_position_size", "max_drawdown",
)
RISK_FIELDS = ("stop_loss_percentage", "max_position_size", "max_drawdown")

FIELD_QUESTIONS = {
    "asset": "which asset to trade (available: S&P 500)",
    "start_date": "the start date of the period",
    "end_date": "the end date of the period",
    "initial_capital": "the initial capital in USD",
    "strategies": "which strategies to use (SMA, RSI, Bollinger Bands or Momentum)",
    "stop_loss_percentage": "the stop-loss percentage",
    "max_position_size": "the maximum position size (% of the portfolio)",
    "max_drawdown": "the maximum drawdown percentage",
}

RISK_LABELS = {
    "stop_loss_percentage": "stop-loss",
    "max_position_size": "maximum position size",
    "max_drawdown": "maximum drawdown",
}

# words the student may use for each value -> canonical value
ASSET_ALIASES = {"sp500": "SP500", "s&p500": "SP500", "s&p": "SP500", "snp500": "SP500", "spx": "SP500"}
STRATEGY_ALIASES = {
    "sma": StrategyType.SMA, "moving average": StrategyType.SMA, "moving averages": StrategyType.SMA,
    "moving average crossover": StrategyType.SMA,
    "rsi": StrategyType.RSI, "relative strength": StrategyType.RSI, "relative strength index": StrategyType.RSI,
    "bollinger": StrategyType.BOLLINGER, "bollinger bands": StrategyType.BOLLINGER,
    "momentum": StrategyType.MOMENTUM,
}
STRATEGY_NAMES = {
    StrategyType.SMA: "SMA", StrategyType.RSI: "RSI",
    StrategyType.BOLLINGER: "Bollinger Bands", StrategyType.MOMENTUM: "Momentum",
}

RELATIVE_PERIOD_RE = re.compile(
    r"\b(last|past|previous|this|current)\s+(\d+\s+)?(year|years|month|months)\b|\byear to date\b|\bytd\b|\bago\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*([km]\b|thousand|million)?", re.IGNORECASE)
_MULTIPLIERS = {"k": 1_000, "thousand": 1_000, "m": 1_000_000, "million": 1_000_000}


def _compact(text: str) -> str:
    return re.sub(r"[\s.\-_]", "", text.lower()).replace("and", "&")


def _mentioned_numbers(description: str) -> list[float]:
    values = []
    for number, suffix in _NUMBER_RE.findall(description):
        value = float(number.replace(",", ""))
        values.append(value * _MULTIPLIERS.get((suffix or "").lower(), 1))
    return values


def _is_mentioned(value: float, description: str) -> bool:
    return any(abs(value - n) < 1e-6 for n in _mentioned_numbers(description))


def to_number(raw) -> float | None:
    """10000, "10,000", "$10k", "5%", "2 million" -> float; anything else -> None."""
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        match = _NUMBER_RE.search(raw.replace("$", ""))
        if match:
            return float(match[1].replace(",", "")) * _MULTIPLIERS.get((match[2] or "").lower(), 1)
    return None


def _asset(raw, description: str) -> tuple[str | None, str | None]:
    if not raw:
        return None, None
    canonical = ASSET_ALIASES.get(_compact(str(raw)))
    if canonical is None:
        return None, f"{raw} is not available; the only asset is the S&P 500."
    mentioned = any(alias in _compact(description) for alias in ASSET_ALIASES)
    return (canonical, None) if mentioned else (None, None)


def to_date(raw, end: bool = False) -> date | None:
    """YYYY-MM-DD as is; a year (2023) or a month (2023-03) -> its first day, or its last day when `end`."""
    text = str(raw).strip()
    try:
        if re.fullmatch(r"\d{4}", text):
            return date(int(text), 12, 31) if end else date(int(text), 1, 1)
        if re.fullmatch(r"\d{4}-\d{2}", text):
            year, month = map(int, text.split("-"))
            if not end:
                return date(year, month, 1)
            return date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _date(raw, description: str, end: bool = False) -> tuple[str | None, str | None]:
    if not raw:
        return None, None
    value = to_date(raw, end)
    if value is None:
        return None, f"I could not read the date \"{raw}\"."
    backed = str(value.year) in description or RELATIVE_PERIOD_RE.search(description)
    return (value.isoformat(), None) if backed else (None, None)


def _strategies(raw, description: str) -> tuple[list[str] | None, str | None]:
    if not raw:
        return None, None
    items = raw if isinstance(raw, list) else [raw]
    text = description.lower()
    found, unknown = [], []  # aliases are matched as whole words ("sma" is not in "small")
    for item in items:
        name = str(item).strip()
        strategy = STRATEGY_ALIASES.get(name.lower())
        if strategy is None:
            unknown.append(name)
        elif any(re.search(rf"\b{re.escape(alias)}\b", text) for alias, s in STRATEGY_ALIASES.items() if s == strategy):
            if strategy.value not in found:
                found.append(strategy.value)
    if unknown:
        return None, (
            f"I don't know the strategy {', '.join(repr(u) for u in unknown)}. "
            "The available ones are SMA, RSI, Bollinger Bands and Momentum."
        )
    return (found or None), None


def _amount(raw, description: str, field: str) -> tuple[float | None, str | None]:
    value = to_number(raw)
    if value is None:
        return None, None
    if not _is_mentioned(value, description):
        return None, None  # the model filled a value the student did not give
    if field == "initial_capital":
        return (value, None) if value > 0 else (None, "The initial capital must be greater than 0.")
    if value <= MIN_PERCENTAGE or value > MAX_PERCENTAGE:  # same rule as the risk step
        return None, f"The {RISK_LABELS[field]} must be greater than 0% and at most 100%."
    return value, None


def coerce(raw: dict, description: str) -> tuple[dict, dict]:
    """Returns (values, problems): values has every field (None when missing), problems maps
    a field to a plain-language message when the student gave something unusable."""
    raw = dict(raw) if isinstance(raw, dict) else {}
    # "during 2023" comes back as start "2023" and no end: the period is that whole year (or month)
    start = str(raw.get("start_date") or "").strip()
    if not raw.get("end_date") and re.fullmatch(r"\d{4}(-\d{2})?", start):
        raw["end_date"] = start
    values, problems = {}, {}
    parsers = {
        "asset": lambda v: _asset(v, description),
        "start_date": lambda v: _date(v, description),
        "end_date": lambda v: _date(v, description, end=True),
        "strategies": lambda v: _strategies(v, description),
    }
    for field in FIELDS:
        parser = parsers.get(field) or (lambda v, f=field: _amount(v, description, f))
        values[field], problem = parser(raw.get(field))
        if problem:
            problems[field] = problem
    return values, problems


def strategy_label(code: str) -> str:
    return STRATEGY_NAMES[StrategyType(code)]
