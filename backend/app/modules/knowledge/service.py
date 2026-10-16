import logging
from functools import lru_cache

from fastapi import HTTPException, status

from app.agents.knowledge.graph import build_knowledge_graph
from app.modules.knowledge import history

logger = logging.getLogger(__name__)

UNAVAILABLE = "The assistant is not available right now. Please try again in a moment."


@lru_cache(maxsize=1)
def _graph():
    # The graph has no per-user state (user_id travels in the input), so one compiled graph serves everyone.
    return build_knowledge_graph()


def ask(user_id: str, message: str) -> dict:
    try:
        result = _graph().invoke({"question": message, "user_id": user_id})
    except Exception:
        # Ollama down or embeddings model missing.
        logger.exception("Knowledge agent failed")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, UNAVAILABLE)

    return {
        "answer": result["answer"],
        "refused": result["refused"],
        "sources": result.get("sources", []),
    }


def get_history(user_id: str) -> dict:
    return {"messages": history.load_history(user_id)}


def reset_history(user_id: str) -> None:
    history.clear_history(user_id)
