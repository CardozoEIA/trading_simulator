# app/agents/compare/tools.py
"""Data access for comparisons (US-27).

The tools are bound to one student: every call checks that the simulation belongs to
them. A slice holds only what a comparison needs (configuration, metrics, benchmark
and highlights), never the full daily data.
"""
import json
import logging

from fastapi import HTTPException
from langchain_core.tools import tool

from app.agents.insights.tools import highlights_for, load_simulation_data
from app.modules.results.service import get_metrics, get_results_summary
from app.modules.simulations.service import (
    build_configuration_summary,
    get_full_configuration,
    get_simulation_history,
    get_simulation_status,
)

logger = logging.getLogger(__name__)

DATABASE_UNAVAILABLE = "Could not connect to the database, please try again"
SLICE_HIGHLIGHTS = ("RISK_STOP", "BEST_TRADE", "WORST_TRADE", "MAX_DRAWDOWN")


def describe(item: dict) -> str:
    """Short label of a simulation, e.g. 'SPY · SMA, RSI · 2023-01-02 to 2023-06-30'."""
    strategies = ", ".join(item.get("strategies") or []) or "n/a"
    return f"{item['asset']} · {strategies} · {item['start_date']} to {item['end_date']}"


def list_my_simulations(user_id: str) -> list[dict]:
    """The student's simulations, newest first (only the fields needed to pick one)."""
    return [
        {
            "id": h["id"],
            "status": h["status"],
            "started_at": str(h["started_at"]),
            "asset": h["asset"],
            "start_date": str(h["start_date"]),
            "end_date": str(h["end_date"]),
            "strategies": h["strategies"],
            "total_return_pct": h["total_return_pct"],
        }
        for h in get_simulation_history(user_id)
    ]


def get_simulation_slice(simulation_id: str, user_id: str) -> dict:
    simulation = get_simulation_status(simulation_id, user_id)  # 404 when missing or not owned
    if simulation["status"] == "RUNNING":
        raise HTTPException(status_code=409, detail="The simulation is still running")

    try:
        try:
            configuration = build_configuration_summary(simulation["configuration_id"], user_id)
            benchmark = configuration["benchmark"]
        except ValueError:
            # no historical candles for the benchmark: compare without it
            configuration, benchmark = get_full_configuration(simulation["configuration_id"], user_id), None
        results = get_results_summary(simulation_id, user_id)
        metrics = get_metrics(simulation_id, user_id).model_dump()
        highlights = [h for h in highlights_for(load_simulation_data(simulation_id)) if h["kind"] in SLICE_HIGHLIGHTS]
    except HTTPException:
        raise
    except LookupError:
        raise HTTPException(status_code=404, detail="Simulation not found")
    except Exception:
        logger.exception("Could not load the slice of simulation %s", simulation_id)
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE)

    risk = configuration["risk"]
    metrics.pop("simulation_id", None)
    return {
        "id": simulation_id,
        "status": simulation["status"],
        "stop_reason": simulation.get("stop_reason"),
        "started_at": str(simulation.get("started_at")),
        "configuration": {
            "asset": configuration["asset"],
            "start_date": str(configuration["start_date"]),
            "end_date": str(configuration["end_date"]),
            "strategies": configuration["strategies"],
            "initial_capital": float(configuration["initial_capital"]),
            "stop_loss_percentage": float(risk["stop_loss_percentage"]),
            "max_position_size": float(risk["max_position_size"]),
            "max_drawdown": float(risk["max_drawdown"]),
        },
        "metrics": {**metrics, "final_value": float(results.final_capital)},
        "benchmark": (
            {"total_return_pct": float(benchmark["total_return_pct"]), "final_capital": float(benchmark["final_capital"])}
            if benchmark else None
        ),
        "highlights": [{"kind": h["kind"], "label": h["label"], "facts": h["facts"]} for h in highlights],
    }


def build_compare_tools(user_id: str):
    """Tools closure-bound to the student, so the agent can never reach another student's data."""

    @tool
    def list_simulations() -> str:
        """The student's own simulations, newest first, as JSON."""
        return json.dumps(list_my_simulations(user_id))

    @tool
    def simulation_slice(simulation_id: str) -> str:
        """Configuration, metrics, buy & hold benchmark and highlights of one of the student's
        simulations, as JSON (not the full daily data)."""
        return json.dumps(get_simulation_slice(simulation_id, user_id))

    return [list_simulations, simulation_slice]
