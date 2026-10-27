# app/modules/agent/traces.py
"""US-31: stores and reads the traceability record of each explanation. Saving is best-effort."""
import logging

from fastapi import HTTPException

from app.core.supabase import supabase_admin as supabase
from app.core.validation import is_valid_uuid

logger = logging.getLogger(__name__)

TABLE = "agent_traces"
MAX_RESULT_LENGTH = 2000


def _clean(trace: list[dict]) -> list[dict]:
    return [
        {
            "tool": entry["tool"],
            "arguments": entry.get("arguments") or {},
            "result": (entry.get("result") or "")[:MAX_RESULT_LENGTH],
        }
        for entry in trace or []
    ]


def save_trace(user_id: str, simulation_id: str, source: str, date: str | None, answer: str,
               trace: list[dict], verification: dict | None) -> None:
    try:
        supabase.table(TABLE).insert({
            "user_id": user_id, "simulation_id": simulation_id, "source": source, "date": date,
            "answer": answer, "tool_calls": _clean(trace), "verification": verification,
        }).execute()
    except Exception:
        logger.exception("Could not save the agent trace (did you run migrations/007_agent_traces.sql?)")


def get_traces(simulation_id: str, user_id: str, date: str | None = None, limit: int = 20) -> list[dict]:
    """Newest first. Only the owner of the simulation can read them."""
    if not is_valid_uuid(simulation_id):
        raise HTTPException(status_code=404, detail="Simulation not found")
    query = supabase.table(TABLE).select("*").eq("simulation_id", simulation_id).eq("user_id", user_id)
    if date:
        query = query.eq("date", date)
    try:
        return query.order("id", desc=True).limit(limit).execute().data
    except Exception:
        raise HTTPException(status_code=503, detail="Could not read the traces")
