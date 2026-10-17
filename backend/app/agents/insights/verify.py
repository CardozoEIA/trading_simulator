# app/agents/insights/verify.py
"""Self-verification for insights: every number and date must come from the facts."""
import re

DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def _numbers(text: str) -> list[float]:
    values = []
    for raw in NUMBER_RE.findall(DATE_RE.sub(" ", text)):
        try:
            values.append(float(raw.replace(",", "")))
        except ValueError:
            continue
    return values


def _is_backed(value: float, allowed: list[float]) -> bool:
    # tolerance covers rounding (e.g. 8.42 -> 8.4) and sign flips like "-6.30%" vs "6.30% drop"
    for fact in allowed:
        if abs(abs(value) - abs(fact)) <= 0.05 + 0.005 * abs(fact):
            return True
    return False


def unverified_values(text: str, facts: str) -> list[str]:
    """Return the dates/numbers in `text` that do not appear in `facts`."""
    problems = []
    fact_dates = set(DATE_RE.findall(facts))
    for found in DATE_RE.findall(text):
        if found not in fact_dates:
            problems.append(found)

    allowed = _numbers(facts)
    for value in _numbers(text):
        if not _is_backed(value, allowed):
            problems.append(f"{value:g}")
    return problems
