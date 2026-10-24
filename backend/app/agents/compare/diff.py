# app/agents/compare/diff.py
"""Pure comparison of two simulation slices (US-27).

Everything shown to the student (values, deltas, which run is better) is computed
here. `diff_facts` turns the result into the sentences the model may use; the
verification step only accepts numbers and dates that appear in them.
"""
from app.agents.compare.tools import describe
from app.agents.insights.facts import money

TIE_TOLERANCE = 0.005

CONFIG_FIELDS = [
    ("asset", "Asset", "text"),
    ("period", "Period", "text"),
    ("strategies", "Strategies", "text"),
    ("initial_capital", "Initial capital", "money"),
    ("stop_loss_percentage", "Stop-loss", "pct"),
    ("max_position_size", "Max position size", "pct"),
    ("max_drawdown", "Max drawdown limit", "pct"),
]

# (key, label, unit, which direction is better)
METRICS = [
    ("total_return_pct", "Total return", "pct", "higher"),
    ("final_value", "Final value", "money", "higher"),
    ("sharpe_ratio", "Sharpe ratio", "ratio", "higher"),
    ("max_drawdown_pct", "Max drawdown", "pct", "lower"),
    ("win_rate", "Win rate", "pct", "higher"),
    ("profit_factor", "Profit factor", "ratio", "higher"),
    ("total_trades", "Completed trades", "count", None),
    ("excess_return_pct", "Return vs buy & hold", "pts", "higher"),
]

DIRECTIONS = {key: direction for key, _, _, direction in METRICS}


def _fmt(value, unit: str) -> str:
    if value is None:
        return "n/a"
    if unit == "money":
        return money(value)
    if unit == "pct":
        return f"{value:.2f}%"
    if unit == "pts":
        return f"{'+' if value > 0 else ''}{value:.2f} pts"
    if unit == "count":
        return str(int(value))
    if unit == "ratio":
        return f"{value:.2f}"
    return str(value)


def _fmt_delta(delta, unit: str) -> str:
    if delta is None:
        return "n/a"
    sign = "+" if delta > 0 else "-" if delta < 0 else ""
    size = abs(delta)
    if unit == "money":
        return f"{sign}{money(size)}"
    if unit in ("pct", "pts"):
        return f"{sign}{size:.2f} pts"
    if unit == "count":
        return f"{sign}{int(size)}"
    return f"{sign}{size:.2f}"


def _config_value(configuration: dict, field: str):
    if field == "period":
        return f"{configuration['start_date']} to {configuration['end_date']}"
    if field == "strategies":
        return ", ".join(configuration.get("strategies") or []) or "n/a"
    return configuration[field]


def configuration_diff(a: dict, b: dict) -> list[dict]:
    rows = []
    for field, label, unit in CONFIG_FIELDS:
        va, vb = _config_value(a, field), _config_value(b, field)
        if field == "strategies":
            changed = sorted(a.get("strategies") or []) != sorted(b.get("strategies") or [])
        else:
            changed = va != vb
        rows.append({
            "field": field, "label": label, "changed": changed,
            "a": _fmt(va, unit), "b": _fmt(vb, unit),
        })
    return rows


def _metric_values(simulation: dict) -> dict:
    """Metric values of one slice; win rate and profit factor do not apply without completed trades."""
    m = simulation["metrics"]
    trades = int(m["total_trades"])
    benchmark = simulation.get("benchmark")
    return {
        "total_return_pct": float(m["total_return_pct"]),
        "final_value": float(m["final_value"]),
        "sharpe_ratio": float(m["sharpe_ratio"]),
        "max_drawdown_pct": float(m["max_drawdown_pct"]),
        "win_rate": float(m["win_rate"]) if trades else None,
        # None with completed trades means "no losing trades": the best possible profit factor
        "profit_factor": (float(m["profit_factor"]) if m["profit_factor"] is not None else float("inf")) if trades else None,
        "total_trades": trades,
        "excess_return_pct": (
            float(m["total_return_pct"]) - float(benchmark["total_return_pct"]) if benchmark else None
        ),
    }


def _better(va, vb, direction: str | None) -> str | None:
    if direction is None or va is None or vb is None:
        return None
    if va == vb or (float("inf") not in (va, vb) and abs(va - vb) <= TIE_TOLERANCE):
        return "tie"
    a_wins = va > vb if direction == "higher" else va < vb
    return "a" if a_wins else "b"


def metrics_diff(a: dict, b: dict) -> list[dict]:
    values_a, values_b = _metric_values(a), _metric_values(b)
    rows = []
    for key, label, unit, direction in METRICS:
        va, vb = values_a[key], values_b[key]
        finite = va is not None and vb is not None and float("inf") not in (va, vb)
        delta = vb - va if finite else None
        rows.append({
            "metric": key, "label": label,
            "a": None if va in (None, float("inf")) else va,
            "b": None if vb in (None, float("inf")) else vb,
            "delta": delta,
            "a_display": "No losing trades" if va == float("inf") else _fmt(va, unit),
            "b_display": "No losing trades" if vb == float("inf") else _fmt(vb, unit),
            "delta_display": _fmt_delta(delta, unit),
            "better": _better(va, vb, direction),
        })
    return rows


def winner(metrics: list[dict]) -> str:
    """The run with the higher total return ("tie" when equal)."""
    total = next(m for m in metrics if m["metric"] == "total_return_pct")
    return total["better"] or "tie"


def diff_facts(a: dict, b: dict, configuration: list[dict], metrics: list[dict], best: str) -> str:
    lines = [
        f"Simulation A: {describe(a['configuration'])}. Status: {a['status']}.",
        f"Simulation B: {describe(b['configuration'])}. Status: {b['status']}.",
    ]

    changed = [c for c in configuration if c["changed"]]
    same = [c["label"].lower() for c in configuration if not c["changed"]]
    if changed:
        lines.append("Configuration differences: " + " ".join(
            f"{c['label']}: A {c['a']}, B {c['b']}." for c in changed
        ))
    else:
        lines.append("Both simulations used exactly the same configuration.")
    if same:
        lines.append(f"Same in both: {', '.join(same)}.")
    if any(c["field"] == "period" and c["changed"] for c in configuration):
        lines.append("The two simulations cover different periods, so the market conditions were different.")

    for m in metrics:
        if m["a_display"] == m["b_display"] == "n/a":
            continue
        line = f"{m['label']}: A {m['a_display']}, B {m['b_display']}"
        if m["delta"] is not None:
            line += f" (difference B minus A: {m['delta_display']})"
        if m["better"] in ("a", "b"):
            side = m["better"].upper()
            line += f", smaller in {side} (better)" if DIRECTIONS[m["metric"]] == "lower" else f", higher in {side} (better)"
        elif m["better"] == "tie":
            line += ", the same in both"
        lines.append(line + ".")

    for name, simulation in (("A", a), ("B", b)):
        for h in simulation.get("highlights") or []:
            lines.append(f"Simulation {name}, {h['label']}: {h['facts']}")

    lines.append(
        "By total return the two simulations tied." if best == "tie"
        else f"By total return, simulation {best.upper()} performed better."
    )
    return "\n".join(lines)
