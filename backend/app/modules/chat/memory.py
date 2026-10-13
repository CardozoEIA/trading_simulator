"""Retrieval-augmented memory (US-25).

A small local model has a small context window, so a long conversation is never replayed in full.
Once the stored history passes HISTORY_THRESHOLD messages, only the earlier turns that are
closest in meaning to the new question are looked up (embedding search) and shown to the model.
"""
import logging
import math

from app.modules.chat import history

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "nomic-embed-text"

HISTORY_THRESHOLD = 20  # stored messages (10 turns). At or below this nothing is retrieved.
TOP_K = 3  # relevant turns shown to the model
RECENT_TURNS_TO_SKIP = 2  # the newest turns are already part of the live conversation
MAX_CHARS_PER_MESSAGE = 300

_embedder = None


def _get_embedder():
    global _embedder

    if _embedder is None:
        from langchain_ollama import OllamaEmbeddings

        _embedder = OllamaEmbeddings(model=EMBEDDING_MODEL, client_kwargs={"timeout": 30})

    return _embedder


def embed_text(text: str) -> list[float] | None:
    """None when the embedding model is not available: memory search is a bonus, never a requirement."""
    try:
        return _get_embedder().embed_query(text)
    except Exception:
        logger.warning(
            "Could not embed text (is the %s model installed? ollama pull %s)",
            EMBEDDING_MODEL,
            EMBEDDING_MODEL,
            exc_info=True,
        )
        return None


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def remember_turn(user_id: str, simulation_id: str, question: str, payload: dict) -> None:
    """Store the turn together with its embedding (the turn is saved even without one)."""
    embedding = embed_text(f"{question}\n{payload['reply']}")

    history.save_turn(user_id, simulation_id, question, payload, embedding=embedding)


def _clip(text: str) -> str:
    text = " ".join(text.split())

    if len(text) <= MAX_CHARS_PER_MESSAGE:
        return text

    return text[: MAX_CHARS_PER_MESSAGE - 1] + "…"


def build_memory_context(user_id: str, simulation_id: str, question: str) -> str | None:
    """The earlier turns most relevant to `question`, or None when the history is still short."""

    if history.count_messages(user_id, simulation_id) <= HISTORY_THRESHOLD:
        return None

    query = embed_text(question)

    if query is None:
        return None

    candidates = history.load_turn_embeddings(user_id, simulation_id)
    older = candidates[:-RECENT_TURNS_TO_SKIP] if RECENT_TURNS_TO_SKIP else candidates

    scored = sorted(
        (
            (cosine(query, row["embedding"]), row["turn_id"])
            for row in older
            if row.get("embedding")
        ),
        reverse=True,
    )[:TOP_K]

    if not scored:
        return None

    rows = history.load_turns(user_id, simulation_id, [turn_id for _, turn_id in scored])

    if not rows:
        return None

    lines = ["Earlier in this conversation (the most relevant turns):"]

    for row in rows:
        speaker = "Student" if row["role"] == "user" else "Assistant"
        lines.append(f"{speaker}: {_clip(row['content'])}")

    return "\n".join(lines)
