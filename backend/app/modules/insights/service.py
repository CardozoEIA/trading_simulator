# app/modules/insights/service.py
"""Proactive highlights (US-26).

What to highlight is computed from the recorded data every time (instant, always
available). The agent's explanation of each highlight is generated in the background
when the simulation finishes and stored in simulation_insights.
"""
import logging
import re
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks, HTTPException

from app.core.supabase import supabase_admin as supabase
from app.core.validation import is_valid_uuid
from app.agents.common.tracing import tracing_config
from app.agents.insights.graph import build_insights_graph
from app.agents.insights.tools import highlights_for, load_simulation_data

logger = logging.getLogger(__name__)

TABLE = "simulation_insights"
STALE_PENDING = timedelta(minutes=5)  # a PENDING row older than this was interrupted

AGENT_UNAVAILABLE = "The agent could not be reached (is Ollama running?)."
NOT_VERIFIABLE = "The agent could not write explanations backed by the simulation data."


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
    _save(simulation_id, status="PENDING", error=None)  # keeps earlier explanations until replaced


def generate_insights(simulation_id: str) -> None:
    """Run the highlights graph and store the explanations. Never raises (background task)."""
    try:
        result = build_insights_graph().invoke(
            {"simulation_id": simulation_id}, config=tracing_config("insights", session_id=simulation_id)
        )
        explanations = result.get("explanations") or {}
        if explanations or not result.get("highlights"):
            _save(simulation_id, status="READY", insights=explanations, error=None, generated_at=_now())
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


def _schedule(simulation_id: str, background_tasks: BackgroundTasks) -> None:
    try:
        mark_pending(simulation_id)
    except Exception:
        logger.exception("Could not write %s (did you run migrations/us26_simulation_insights.sql?)", TABLE)
        raise HTTPException(status_code=503, detail="Insights are not available right now, please try again")
    background_tasks.add_task(generate_insights, simulation_id)


def get_insights(simulation_id: str, user_id: str, background_tasks: BackgroundTasks) -> dict:
    simulation = _ensure_owner(simulation_id, user_id)
    if simulation["status"] == "RUNNING":
        return {"simulation_id": simulation_id, "status": "PENDING", "highlights": []}

    try:
        highlights = highlights_for(load_simulation_data(simulation_id))
        rows = supabase.table(TABLE).select("*").eq("simulation_id", simulation_id).limit(1).execute().data
    except Exception:
        logger.exception("Could not load highlights (did you run migrations/us26_simulation_insights.sql?)")
        raise HTTPException(status_code=503, detail="Insights are not available right now, please try again")

    if not rows:
        # Simulations that finished before US-26 (or whose trigger failed) get explained on first view.
        if highlights:
            _schedule(simulation_id, background_tasks)
        status, error, explanations = "PENDING", None, {}
    else:
        row = rows[0]
        status, error, explanations = row["status"], row.get("error"), row.get("insights") or {}
        if status == "PENDING" and datetime.now(timezone.utc) - _parse_ts(row["updated_at"]) > STALE_PENDING:
            status, error = "FAILED", "Generating the explanations took too long."

    if not highlights:
        status = "READY"
    for h in highlights:
        explained = explanations.get(h["kind"]) if isinstance(explanations, dict) else None
        if explained:
            h["title"], h["explanation"] = explained["title"], explained["detail"]
    return {"simulation_id": simulation_id, "status": status, "highlights": highlights, "error": error}


def request_generation(simulation_id: str, user_id: str, background_tasks: BackgroundTasks) -> dict:
    """Manual retry, e.g. after Ollama was down when the run finished."""
    simulation = _ensure_owner(simulation_id, user_id)
    if simulation["status"] == "RUNNING":
        raise HTTPException(status_code=409, detail="The simulation is still running")
    _schedule(simulation_id, background_tasks)
    return get_insights(simulation_id, user_id, BackgroundTasks())
