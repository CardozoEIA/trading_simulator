# app/agents/compare/verify.py
"""Direction check for comparisons: numbers are verified elsewhere, this catches text that
says the wrong run had the larger or smaller value (e.g. "B had a larger drawdown" when B's
drawdown was the smaller one), a mistake the local model makes even with correct facts."""
import re

_METRICS = {
    "max_drawdown_pct": r"(?:max(?:imum)? )?drawdown",
    "total_return_pct": r"(?:total )?returns?",
    "sharpe_ratio": r"sharpe ratio",
    "win_rate": r"win rate",
    "profit_factor": r"profit factor",
}
_MORE = r"larger|bigger|higher|greater|deeper"
_LESS = r"smaller|lower|shallower"
_COMPARATIVE = rf"(?P<word>{_MORE}|{_LESS})"
_SIDE = r"(?:simulation |run )?(?P<side>[AB])\b"
_FILLER = r"(?:slightly |much |a bit |considerably )?"


def _patterns(metric_re: str) -> list[re.Pattern]:
    return [
        # "larger drawdown in Simulation B"
        re.compile(rf"\b{_FILLER}{_COMPARATIVE} {metric_re} (?:in|for|of) {_SIDE}", re.IGNORECASE),
        # "Simulation B had a larger drawdown", "B's higher Sharpe ratio"
        re.compile(
            rf"\b{_SIDE}(?:'s)? (?:had |has |showed |with )?(?:a |an |the )?{_FILLER}{_COMPARATIVE} {metric_re}\b",
            re.IGNORECASE,
        ),
    ]


def wrong_directions(text: str, metrics: list[dict]) -> list[str]:
    """Claims in `text` that contradict the computed values (A and B of each metric)."""
    values = {m["metric"]: (m["a"], m["b"]) for m in metrics}
    problems = []
    for metric, metric_re in _METRICS.items():
        a, b = values.get(metric, (None, None))
        if a is None or b is None or a == b:
            continue
        for pattern in _patterns(metric_re):
            for match in pattern.finditer(text):
                side = match["side"].upper()
                claims_more = re.fullmatch(_MORE, match["word"], re.IGNORECASE) is not None
                mine, other = (a, b) if side == "A" else (b, a)
                if claims_more != (mine > other):
                    problems.append(match.group(0).strip())
    return problems
