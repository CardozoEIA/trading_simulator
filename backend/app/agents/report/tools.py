# app/agents/report/tools.py
"""Data access for the report: reuses the existing services and insight tools, so the
report is built only from recorded data the student owns."""
from app.agents.insights.tools import highlights_for, load_simulation_data
from app.modules.results.service import get_metrics, get_results_summary
from app.modules.simulations.service import build_configuration_summary, get_full_configuration


def load_report_data(simulation: dict, user_id: str) -> dict:
    """`simulation` is the owned row returned by get_simulation_status."""
    simulation_id = simulation["id"]
    try:
        configuration = build_configuration_summary(simulation["configuration_id"], user_id)
    except ValueError:
        # no historical candles for the benchmark: the report is still built without it
        configuration = {**get_full_configuration(simulation["configuration_id"], user_id), "benchmark": None}

    recorded = load_simulation_data(simulation_id)
    return {
        "simulation": simulation,
        "configuration": configuration,
        "results": get_results_summary(simulation_id, user_id).model_dump(),
        "metrics": get_metrics(simulation_id, user_id).model_dump(),
        "trades": recorded["trades"],
        "highlights": highlights_for(recorded),
    }
