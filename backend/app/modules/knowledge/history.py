"""Conversation history of the knowledge-base chat."""
import logging
import uuid

from app.core.supabase import supabase_admin as supabase

logger = logging.getLogger(__name__)

TABLE = "kb_messages"


def save_turn(user_id: str, question: str, answer: str, refused: bool, sources: list[dict]) -> None:
    turn_id = str(uuid.uuid4())

    supabase.table(TABLE).insert(
        [
            {"user_id": user_id, "turn_id": turn_id, "role": "user", "content": question},
            {
                "user_id": user_id,
                "turn_id": turn_id,
                "role": "assistant",
                "content": answer,
                "refused": refused,
                "sources": sources,
            },
        ]
    ).execute()


def load_history(user_id: str, limit: int = 50) -> list[dict]:
    """The last `limit` messages, oldest first."""
    rows = (
        supabase.table(TABLE)
        .select("role, content, refused, sources")
        .eq("user_id", user_id)
        .order("id", desc=True)
        .limit(limit)
        .execute()
        .data
    )

    return list(reversed(rows or []))


def clear_history(user_id: str) -> None:
    supabase.table(TABLE).delete().eq("user_id", user_id).execute()
