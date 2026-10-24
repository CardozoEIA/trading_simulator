# app/agents/insights/verify.py
"""Self-verification for insights: every number and date must come from the facts."""
import re

DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
NUMBER_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}
_MONTH = r"(january|february|march|april|may|june|july|august|september|october|november|december)"
WRITTEN_DATE_RE = re.compile(rf"\b{_MONTH}\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.IGNORECASE)
WRITTEN_DATE_DMY_RE = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH},?\s+(\d{{4}})\b", re.IGNORECASE)

# results of a past backtest must never read as a promise about the future
FORWARD_LOOKING_RE = re.compile(
    r"\b(guarantee\w*|promis\w*|will (?:always|continue|keep|make|earn|beat|outperform)|"
    r"you should (?:buy|sell|invest))\b",
    re.IGNORECASE,
)


def iso_dates(text: str) -> str:
    """'October 14, 2023' -> '2023-10-14', so written-out dates are checked as dates, not as numbers."""
    text = WRITTEN_DATE_RE.sub(lambda m: f"{m[3]}-{MONTHS[m[1].lower()]:02d}-{int(m[2]):02d}", text)
    return WRITTEN_DATE_DMY_RE.sub(lambda m: f"{m[3]}-{MONTHS[m[2].lower()]:02d}-{int(m[1]):02d}", text)


def makes_promises(text: str) -> bool:
    return bool(FORWARD_LOOKING_RE.search(text))


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
    text = iso_dates(text)
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
