# app/modules/setup/service.py
"""Natural-language setup (US-29). Parses and validates only: nothing is written."""
import logging

from fastapi import HTTPException

from app.agents.setup.graph import build_setup_graph

logger = logging.getLogger(__name__)

AGENT_UNAVAILABLE = "The agent could not be reached to read your description (is Ollama running?). Please try again."


def parse_setup(description: str, llm=None, today=None) -> dict:
    try:
        result = build_setup_graph(llm=llm, today=today).invoke({"description": description})
    except HTTPException:
        raise  # 503 from the database while checking data availability
    except Exception:
        logger.exception("Setup parsing failed")
        raise HTTPException(status_code=503, detail=AGENT_UNAVAILABLE)

    return {
        "status": result["status"],
        "proposal": result["values"],
        "missing_fields": result["missing_fields"],
        "message": result["message"],
    }
