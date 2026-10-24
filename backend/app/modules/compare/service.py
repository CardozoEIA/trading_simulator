# app/modules/compare/service.py
"""Comparison of two of the student's simulations (US-27)."""
import logging

from fastapi import HTTPException

from app.agents.compare.graph import build_compare_graph
from app.agents.compare.tools import describe

logger = logging.getLogger(__name__)

AGENT_UNAVAILABLE = "The agent could not be reached to compare the simulations (is Ollama running?). Please try again."


def _summary(simulation: dict) -> dict:
    return {
        "id": simulation["id"],
        "label": describe(simulation["configuration"]),
        "status": simulation["status"],
        "started_at": simulation.get("started_at"),
    }


def compare_simulations(simulation_a: str, simulation_b: str, user_id: str, llm=None) -> dict:
    if simulation_a == simulation_b:
        raise HTTPException(status_code=400, detail="Choose two different simulations to compare")

    try:
        result = build_compare_graph(llm=llm).invoke(
            {"user_id": user_id, "simulation_a": simulation_a, "simulation_b": simulation_b}
        )
    except HTTPException:
        raise  # 404 not found / not owned, 409 still running, 503 database
    except Exception:
        logger.exception("Comparison failed for %s vs %s", simulation_a, simulation_b)
        raise HTTPException(status_code=503, detail=AGENT_UNAVAILABLE)

    return {
        "simulation_a": _summary(result["slice_a"]),
        "simulation_b": _summary(result["slice_b"]),
        "configuration_diff": result["configuration_diff"],
        "metrics_diff": result["metrics_diff"],
        "winner": result["winner"],
        "explanation": result.get("explanation"),
    }
