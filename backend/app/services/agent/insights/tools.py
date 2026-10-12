# app/services/agent/insights/tools.py
"""Data tools for the insights graph. Each one reads recorded simulation data and
returns plain text built by the pure functions in facts.py."""
from functools import lru_cache

from langchain_core.tools import tool

from app.core.supabase import supabase_admin as supabase
from app.services.agent.insights.facts import (
    buy_and_hold_text,
    drawdown_text,
    run_summary_text,
    trade_performance_text,
)


def build_insight_tools(simulation_id: str):

    @lru_cache(maxsize=1)
    def run_info() -> dict:
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
        return {**sim[0], **config[0]}

    @lru_cache(maxsize=1)
    def equity() -> list[dict]:
        return (
            supabase.table("simulation_equity_curve")
            .select("date, portfolio_value")
            .eq("simulation_id", simulation_id).order("date").execute()
        ).data

    @tool
    def get_run_summary() -> str:
        """Asset, period, strategies and whether the run finished or was stopped by risk."""
        info = run_info()
        return run_summary_text(
            status=info["status"],
            stop_reason=info.get("stop_reason"),
            strategies=info.get("strategies") or [],
            asset=info["asset"],
            start_date=str(info["start_date"]),
            end_date=str(info["end_date"]),
        )

    @tool
    def get_trade_performance() -> str:
        """Number of trades and the best and worst completed round-trips."""
        trades = (
            supabase.table("simulation_trades")
            .select("date, type, price, quantity")
            .eq("simulation_id", simulation_id).order("date").execute()
        ).data
        return trade_performance_text(trades)

    @tool
    def get_drawdown() -> str:
        """Final value, total return, highest value and the largest drawdown with its dates."""
        return drawdown_text(equity(), float(run_info()["initial_capital"]))

    @tool
    def get_buy_and_hold_comparison() -> str:
        """Compares the strategy's return with simply buying and holding the asset."""
        prices = (
            supabase.table("simulation_signals")
            .select("date, price")
            .eq("simulation_id", simulation_id).order("date").execute()
        ).data
        curve = equity()
        final_value = float(curve[-1]["portfolio_value"]) if curve else None
        return buy_and_hold_text(prices, float(run_info()["initial_capital"]), final_value)

    return [get_run_summary, get_trade_performance, get_drawdown, get_buy_and_hold_comparison]
