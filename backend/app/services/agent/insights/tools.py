# app/services/agent/insights/tools.py
"""Data access for the highlights: reads the recorded simulation once and exposes it
to the graph as tools (the agent never reads anything else)."""
import json

from langchain_core.tools import tool

from app.core.supabase import supabase_admin as supabase
from app.services.agent.insights.facts import compute_highlights, overview_text


def load_simulation_data(simulation_id: str) -> dict:
    sim = (
        supabase.table("simulations")
        .select("configuration_id, status, stop_reason")
        .eq("id", simulation_id).limit(1).execute()
    ).data
    if not sim:
        raise LookupError("Simulation not found.")
    config = (
        supabase.table("backtest_configurations")
        .select("asset, start_date, end_date, initial_capital, strategies")
        .eq("id", sim[0]["configuration_id"]).limit(1).execute()
    ).data
    if not config:
        raise LookupError("Simulation configuration not found.")

    def rows(table: str, columns: str) -> list[dict]:
        return (
            supabase.table(table).select(columns)
            .eq("simulation_id", simulation_id).order("date").execute()
        ).data

    return {
        "run": {**sim[0], **config[0]},
        "trades": rows("simulation_trades", "date, type, price, quantity"),
        "equity": rows("simulation_equity_curve", "date, portfolio_value"),
        "prices": rows("simulation_signals", "date, price"),
    }


def highlights_for(data: dict) -> list[dict]:
    return compute_highlights(data["run"], data["trades"], data["equity"], data["prices"])


def build_insight_tools(simulation_id: str):
    data = load_simulation_data(simulation_id)

    @tool
    def get_run_overview() -> str:
        """Asset, period, strategies, initial capital, final value and total return."""
        return overview_text(data["run"], data["equity"])

    @tool
    def find_highlights() -> str:
        """The notable points of the run (best/worst trade, largest drop, buy & hold, risk stop)
        with the recorded facts behind each one, as JSON."""
        return json.dumps(highlights_for(data))

    return [get_run_overview, find_highlights]
