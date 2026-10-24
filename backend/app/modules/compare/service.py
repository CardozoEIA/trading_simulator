# app/modules/compare/service.py
"""Comparison of two of the student's simulations (US-27)."""
import logging

from fastapi import HTTPException

from app.agents.compare.diff import configuration_diff, metrics_diff, winner
from app.agents.compare.graph import build_compare_graph
from app.agents.compare.tools import describe, get_simulation_slice

logger = logging.getLogger(__name__)

AGENT_UNAVAILABLE = "The agent could not be reached to compare the simulations (is Ollama running?). Please try again."


def _summary(simulation: dict) -> dict:
    return {
        "id": simulation["id"],
        "label": describe(simulation["configuration"]),
        "status": simulation["status"],
        "started_at": simulation.get("started_at"),
    }


def _payload(slice_a: dict, slice_b: dict, configuration: list[dict], metrics: list[dict],
             best: str, explanation: str | None) -> dict:
    return {
        "simulation_a": _summary(slice_a),
        "simulation_b": _summary(slice_b),
        "configuration_diff": configuration,
        "metrics_diff": metrics,
        "winner": best,
        "explanation": explanation,
    }


def _check_pair(simulation_a: str, simulation_b: str) -> None:
    if simulation_a == simulation_b:
        raise HTTPException(status_code=400, detail="Choose two different simulations to compare")


def compare_simulations(simulation_a: str, simulation_b: str, user_id: str, llm=None) -> dict:
    _check_pair(simulation_a, simulation_b)

    try:
        result = build_compare_graph(llm=llm).invoke(
            {"user_id": user_id, "simulation_a": simulation_a, "simulation_b": simulation_b}
        )
    except HTTPException:
        raise  # 404 not found / not owned, 409 still running, 503 database
    except Exception:
        logger.exception("Comparison failed for %s vs %s", simulation_a, simulation_b)
        raise HTTPException(status_code=503, detail=AGENT_UNAVAILABLE)

    return _payload(
        result["slice_a"], result["slice_b"], result["configuration_diff"],
        result["metrics_diff"], result["winner"], result.get("explanation"),
    )


def compare_without_explanation(simulation_a: str, simulation_b: str, user_id: str) -> dict:
    """The computed comparison only (no model call), for when the agent is unavailable."""
    _check_pair(simulation_a, simulation_b)
    slice_a, slice_b = get_simulation_slice(simulation_a, user_id), get_simulation_slice(simulation_b, user_id)
    metrics = metrics_diff(slice_a, slice_b)
    return _payload(
        slice_a, slice_b, configuration_diff(slice_a["configuration"], slice_b["configuration"]),
        metrics, winner(metrics), None,
    )
