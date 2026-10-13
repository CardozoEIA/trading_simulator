"""Persistent conversation history (US-25). Saving is best-effort: a database hiccup must not break the chat."""
import logging
import uuid

from fastapi import HTTPException

from app.core.supabase import supabase_admin as supabase

logger = logging.getLogger(__name__)

TABLE = "chat_messages"
MAX_CANDIDATE_TURNS = 200  # newest turns considered by the relevance search


def load_history(user_id: str, simulation_id: str, limit: int = 50) -> list[dict]:
    """The last `limit` messages of this student's conversation, oldest first."""
    try:
        rows = (
            supabase.table(TABLE)
            .select("role, content, route, date")
            .eq("user_id", user_id)
            .eq("simulation_id", simulation_id)
            .order("id", desc=True)
            .limit(limit)
            .execute()
            .data
        )
    except Exception:
        logger.exception("Could not load the chat history (did you run migrations/us25_chat_messages.sql?)")
        return []

    return list(reversed(rows or []))


def save_turn(
    user_id: str,
    simulation_id: str,
    question: str,
    payload: dict,
    embedding: list[float] | None = None,
) -> None:
    turn_id = str(uuid.uuid4())

    rows = [
        {
            "user_id": user_id,
            "simulation_id": simulation_id,
            "turn_id": turn_id,
            "role": "user",
            "content": question,
            "route": None,
            "date": None,
            "embedding": None,
        },
        {
            "user_id": user_id,
            "simulation_id": simulation_id,
            "turn_id": turn_id,
            "role": "assistant",
            "content": payload["reply"],
            "route": payload.get("route"),
            "date": payload.get("date"),
            "embedding": embedding,  # one embedding per turn, kept on the answer row
        },
    ]

    try:
        supabase.table(TABLE).insert(rows).execute()
    except Exception:
        logger.exception("Could not save the chat turn (did you run migrations/us25_chat_messages.sql?)")


def count_messages(user_id: str, simulation_id: str) -> int:
    try:
        response = (
            supabase.table(TABLE)
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("simulation_id", simulation_id)
            .limit(1)
            .execute()
        )
    except Exception:
        logger.exception("Could not count the chat messages")
        return 0

    return response.count or 0


def load_turn_embeddings(user_id: str, simulation_id: str) -> list[dict]:
    """[{turn_id, embedding}] of the newest turns, oldest first."""
    try:
        rows = (
            supabase.table(TABLE)
            .select("turn_id, embedding")
            .eq("user_id", user_id)
            .eq("simulation_id", simulation_id)
            .eq("role", "assistant")
            .not_.is_("embedding", "null")
            .order("id", desc=True)
            .limit(MAX_CANDIDATE_TURNS)
            .execute()
            .data
        )
    except Exception:
        logger.exception("Could not load the turn embeddings")
        return []

    return list(reversed(rows or []))


def load_turns(user_id: str, simulation_id: str, turn_ids: list[str]) -> list[dict]:
    """Both messages of the given turns, oldest first."""
    if not turn_ids:
        return []

    try:
        return (
            supabase.table(TABLE)
            .select("turn_id, role, content")
            .eq("user_id", user_id)
            .eq("simulation_id", simulation_id)
            .in_("turn_id", turn_ids)
            .order("id")
            .execute()
            .data
        ) or []
    except Exception:
        logger.exception("Could not load the relevant turns")
        return []


def clear_history(user_id: str, simulation_id: str) -> None:
    try:
        (
            supabase.table(TABLE)
            .delete()
            .eq("user_id", user_id)
            .eq("simulation_id", simulation_id)
            .execute()
        )
    except Exception:
        logger.exception("Could not clear the chat history")
        raise HTTPException(
            status_code=503,
            detail="Could not clear the conversation right now, please try again.",
        )
