# app/modules/insights/service.py
"""Proactive insights (US-26): generated when a simulation finishes, stored, and read by
the results view. Generation runs in the background and never blocks the results."""
import logging
import re
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.core.supabase import supabase_admin as supabase
from app.core.validation import is_valid_uuid
from app.services.agent.insights.graph import build_insights_graph

logger = logging.getLogger(__name__)

TABLE = "simulation_insights"
STALE_PENDING = timedelta(minutes=5)  # a PENDING row older than this was interrupted

AGENT_UNAVAILABLE = "The agent could not be reached. Make sure the local model (Ollama) is running and try again."
NOT_VERIFIABLE = "The agent could not produce insights backed by the simulation data. Try again."


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_ts(value: str) -> datetime:
    """Postgres timestamps may have 1-6 fractional digits; older Pythons need exactly 6."""
    value = value.replace("Z", "+00:00")
    match = re.match(r"^(.*?\.)(\d+)(.*)$", value)
    if match:
        value = match.group(1) + match.group(2)[:6].ljust(6, "0") + match.group(3)
    return datetime.fromisoformat(value)


def _save(simulation_id: str, **fields) -> None:
    supabase.table(TABLE).upsert({"simulation_id": simulation_id, "updated_at": _now(), **fields}).execute()


def _ensure_owner(simulation_id: str, user_id: str) -> dict:
    if not is_valid_uuid(simulation_id):
        raise HTTPException(status_code=404, detail="Simulation not found")
    try:
        response = (
            supabase.table("simulations").select("id, status")
            .eq("id", simulation_id).eq("user_id", user_id).limit(1).execute()
        )
    except Exception:
        logger.exception("Could not verify simulation ownership")
        raise HTTPException(status_code=503, detail="Could not connect to the database, please try again")
    if not response.data:
        raise HTTPException(status_code=404, detail="Simulation not found")
    return response.data[0]


def mark_pending(simulation_id: str) -> None:
    _save(simulation_id, status="PENDING", insights=None, error=None, generated_at=None)


def generate_insights(simulation_id: str) -> None:
    """Run the insights graph and store the outcome. Never raises (background task)."""
    try:
        result = build_insights_graph().invoke({"simulation_id": simulation_id})
        insights = result.get("insights") or []
        if insights:
            _save(simulation_id, status="READY", insights=insights, error=None, generated_at=_now())
        else:
            _save(simulation_id, status="FAILED", error=NOT_VERIFIABLE)
    except Exception:
        logger.exception("Insight generation failed for simulation %s", simulation_id)
        try:
            _save(simulation_id, status="FAILED", error=AGENT_UNAVAILABLE)
        except Exception:
            logger.exception("Could not record the insight failure")


def on_simulation_finished(simulation_id: str) -> None:
    """Event entry point: called when a run reaches FINISHED or STOPPED_BY_RISK."""
    generate_insights(simulation_id)


def get_insights(simulation_id: str, user_id: str) -> dict:
    _ensure_owner(simulation_id, user_id)
    try:
        response = supabase.table(TABLE).select("*").eq("simulation_id", simulation_id).limit(1).execute()
    except Exception:
        logger.exception("Could not read %s (did you run migrations/us26_simulation_insights.sql?)", TABLE)
        raise HTTPException(status_code=503, detail="Insights are not available right now, please try again")
    if not response.data:
        return {"simulation_id": simulation_id, "status": "NOT_GENERATED"}

    row = response.data[0]
    status = row["status"]
    updated_at = _parse_ts(row["updated_at"])
    if status == "PENDING" and datetime.now(timezone.utc) - updated_at > STALE_PENDING:
        status, row["error"] = "FAILED", "Generating the insights took too long. Try again."
    return {
        "simulation_id": simulation_id,
        "status": status,
        "insights": row.get("insights") or [],
        "error": row.get("error"),
        "generated_at": row.get("generated_at"),
    }


def request_generation(simulation_id: str, user_id: str) -> dict:
    """Manual (re)generation, e.g. after Ollama was down when the run finished."""
    simulation = _ensure_owner(simulation_id, user_id)
    if simulation["status"] == "RUNNING":
        raise HTTPException(status_code=409, detail="The simulation is still running")
    current = get_insights(simulation_id, user_id)
    if current["status"] == "PENDING":
        raise HTTPException(status_code=409, detail="Insights are already being generated")
    try:
        mark_pending(simulation_id)
    except Exception:
        logger.exception("Could not write %s", TABLE)
        raise HTTPException(status_code=503, detail="Could not connect to the database, please try again")
    return {"simulation_id": simulation_id, "status": "PENDING"}
