"""LangGraph checkpointer for the conversation (US-25).

With SUPABASE_DB_URL set, the conversation state (messages and last discussed day) lives in
Supabase Postgres, so it survives page reloads and backend restarts. Without it, the app still
works with an in-memory saver, which forgets everything when the server stops.
"""
import logging
import os
from threading import Lock

from dotenv import load_dotenv
from langgraph.checkpoint.memory import MemorySaver

load_dotenv()

logger = logging.getLogger(__name__)

# Tables created by PostgresSaver.setup()
CHECKPOINT_TABLES = (
    "checkpoints",
    "checkpoint_blobs",
    "checkpoint_writes",
    "checkpoint_migrations",
)

_lock = Lock()
_checkpointer = None


def _lock_down_tables(pool) -> None:
    """Supabase serves every table of the public schema through its REST API.

    Row level security without policies closes that door, so nobody can read another student's
    conversation with the public key. The backend connects directly to Postgres as the table
    owner, so it is not affected.
    """
    with pool.connection() as connection:
        for table in CHECKPOINT_TABLES:
            connection.execute(f"alter table public.{table} enable row level security")


def _build_postgres_checkpointer(db_url: str):
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    pool = ConnectionPool(
        conninfo=db_url,
        min_size=1,
        max_size=5,
        kwargs={
            "autocommit": True,
            "prepare_threshold": None,  # required by Supabase's transaction pooler
            "row_factory": dict_row,
        },
        open=True,
    )

    saver = PostgresSaver(pool)
    saver.setup()  # creates the checkpoint tables the first time
    _lock_down_tables(pool)

    return saver


def _create():
    db_url = os.getenv("SUPABASE_DB_URL")

    if not db_url:
        logger.warning(
            "SUPABASE_DB_URL is not set: the live conversation memory is kept in RAM and is lost "
            "when the server restarts (the history is still reloaded from chat_messages)."
        )
        return MemorySaver()

    try:
        saver = _build_postgres_checkpointer(db_url)
        logger.info("Conversation memory: Postgres checkpointer ready")
        return saver
    except Exception:
        logger.exception("Could not start the Postgres checkpointer, falling back to memory")
        return MemorySaver()


def get_checkpointer():
    """One checkpointer for the whole process, created on first use."""
    global _checkpointer

    with _lock:
        if _checkpointer is None:
            _checkpointer = _create()

        return _checkpointer
