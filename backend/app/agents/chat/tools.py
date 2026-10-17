from app.core.supabase import supabase_admin as supabase

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