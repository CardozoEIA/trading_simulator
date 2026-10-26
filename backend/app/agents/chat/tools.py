from app.core.supabase import supabase_admin as supabase

from app.agents.compare.graph import build_compare_graph
from app.agents.compare.tools import describe

from app.agents.insights.facts import overview_text
from app.agents.insights.tools import (
    highlights_for,
    load_simulation_data,
)


def summarize_simulation(simulation_id: str) -> str:
    """Overview plus one line per highlight. Details live in the highlight pop-ups of the results page."""

    data = load_simulation_data(simulation_id)

    lines = [overview_text(data["run"], data["equity"])]

    highlights = highlights_for(data)

    if highlights:
        lines.append("Highlights:")
        lines.extend(f"- {h['label']}" for h in highlights)
        lines.append("Click a highlight on this page to read its full explanation.")

    return "\n".join(lines)


def buy_and_hold_comparison(simulation_id: str) -> str:

    data = load_simulation_data(simulation_id)

    highlights = highlights_for(data)

    highlight = next(
        (
            h
            for h in highlights
            if h.get("kind") == "BUY_AND_HOLD"
        ),
        None,
    )

    if highlight is None:
        return (
            "The buy and hold comparison is not available "
            "for this simulation."
        )

    return (
        f"{highlight['label']}. "
        f"{highlight['facts']}"
    )


def current_risk_values(simulation_id: str) -> dict | None:
    """The risk limits this simulation was run with, or None if they cannot be found."""

    simulation = (
        supabase.table("simulations")
        .select("configuration_id")
        .eq("id", simulation_id)
        .limit(1)
        .execute()
        .data
    )

    if not simulation:
        return None

    risk = (
        supabase.table("risk_configurations")
        .select("stop_loss_percentage, max_position_size, max_drawdown")
        .eq("configuration_id", simulation[0]["configuration_id"])
        .limit(1)
        .execute()
        .data
    )

    return risk[0] if risk else None


COMPARE_LINES = ("total_return_pct", "sharpe_ratio", "max_drawdown_pct", "excess_return_pct")


def compare_simulations_text(simulation_id: str, other_id: str, user_id: str, config: dict | None = None) -> str:
    """Chat reply for "compare this run with ...": key metrics side by side plus the verified explanation."""

    result = build_compare_graph().invoke(
        {"user_id": user_id, "simulation_a": simulation_id, "simulation_b": other_id},
        config=config,
    )

    metrics = {m["metric"]: m for m in result["metrics_diff"]}

    lines = [f"Compared with {describe(result['slice_b']['configuration'])} (A is this run, B the other one):"]
    lines.extend(
        f"- {metrics[key]['label']}: this run {metrics[key]['a_display']}, the other {metrics[key]['b_display']}"
        for key in COMPARE_LINES
        if metrics[key]["a_display"] != "n/a" or metrics[key]["b_display"] != "n/a"
    )

    lines.append(
        result.get("explanation")
        or "I could not write an explanation backed by the data, but the figures above are from both simulations."
    )
    lines.append("Open History and select both runs to see the full side-by-side comparison.")

    return "\n".join(lines)
