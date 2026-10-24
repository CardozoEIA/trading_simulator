# app/modules/whatif/service.py
"""What-if re-run (US-28). Only reached after the student confirmed the plan in the UI."""
import logging

from fastapi import HTTPException

from app.agents.whatif.graph import build_what_if_graph

logger = logging.getLogger(__name__)

DATABASE_UNAVAILABLE = "Could not connect to the database, please try again"


def run_what_if(simulation_id: str, user_id: str, parameter: str, value: float, **graph_options) -> dict:
    try:
        result = build_what_if_graph(**graph_options).invoke(
            {"user_id": user_id, "simulation_id": simulation_id, "parameter": parameter, "value": value}
        )
    except HTTPException:
        raise  # 400 invalid change, 404 not owned, 409 still running, 503 database
    except Exception:
        logger.exception("What-if failed for simulation %s", simulation_id)
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE)

    completed = bool(result.get("what_if_id"))
    return {
        "status": "COMPLETED" if completed else "FALLBACK",
        "original_id": simulation_id,
        "what_if_id": result.get("what_if_id"),
        "change": result["proposal"],
        "comparison": result.get("comparison"),
        "fallback": result.get("fallback"),
        "message": result.get("message", ""),
    }
