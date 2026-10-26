# app/modules/report/service.py
"""Shareable simulation report (US-32).

Figures and tables come from the recorded data; the agent only adds a verified
narrative per section. Nothing is stored: the report is generated on request.
"""
import logging
from datetime import datetime, timezone

from fastapi import HTTPException

from app.agents.common.tracing import tracing_config
from app.agents.report.graph import build_report_graph
from app.agents.report.render import render_markdown
from app.agents.report.tools import load_report_data
from app.modules.simulations.service import get_simulation_status

logger = logging.getLogger(__name__)

DATABASE_UNAVAILABLE = "Could not connect to the database, please try again"
AGENT_UNAVAILABLE = "The agent could not be reached to write the report (is Ollama running?). Please try again."


def generate_report(simulation_id: str, user_id: str, llm=None) -> dict:
    simulation = get_simulation_status(simulation_id, user_id)  # 404 when missing or not owned
    if simulation["status"] == "RUNNING":
        raise HTTPException(status_code=409, detail="The simulation is still running")

    try:
        data = load_report_data(simulation, user_id)
    except HTTPException:
        raise
    except LookupError:
        raise HTTPException(status_code=404, detail="Simulation not found")
    except Exception:
        logger.exception("Could not load the report data for simulation %s", simulation_id)
        raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE)

    try:
        result = build_report_graph(llm=llm).invoke(
            {"data": data}, config=tracing_config("report", user_id, simulation_id)
        )
    except Exception:
        logger.exception("Report generation failed for simulation %s", simulation_id)
        raise HTTPException(status_code=503, detail=AGENT_UNAVAILABLE)

    narratives = result.get("narratives") or {}
    sections = [
        {**s, "narrative": s["narrative"] or narratives.get(s["key"])}
        for s in result["sections"]
    ]
    for s in sections:
        s.pop("facts", None)

    title = f"Simulation report: {data['configuration']['asset']}"
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return {
        "simulation_id": simulation_id,
        "title": title,
        "generated_at": generated_at,
        "markdown": render_markdown(title, generated_at, simulation_id, sections),
        "sections": sections,
    }
