from datetime import date, datetime, timezone

from fastapi import HTTPException

from app.services.historical_data.processor import process_historical_data
from app.services.strategy.engine import run_strategy
from app.services.strategy.strategies.sma import evaluate as sma_evaluate
from app.services.strategy.schema import DecisionAction

from app.core.supabase import supabase_admin as supabase
from app.core.validation import is_valid_uuid
from app.modules.portfolio.service import run_portfolio, save_trades
from app.modules.decisions.service import save_decisions


def get_full_configuration(configuration_id: str, user_id: str) -> dict:
    """Joins backtest_configurations + risk_configurations for a given configuration.

    This is the point where the pieces saved separately during US-03/US-04/US-06
    come together into a single configuration object. Used both to show the
    confirmation summary (US-05) and to start a simulation (US-07).
    """
    if not is_valid_uuid(configuration_id):
        raise HTTPException(
            status_code=404,
            detail="The referenced simulation configuration was not found"
        )

    try:
        config_response = (
            supabase
            .table("backtest_configurations")
            .select("*")
            .eq("id", configuration_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the database, please try again"
        )

    if not config_response.data:
        raise HTTPException(
            status_code=404,
            detail="The referenced simulation configuration was not found"
        )

    try:
        risk_response = (
            supabase
            .table("risk_configurations")
            .select("*")
            .eq("configuration_id", configuration_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the database, please try again"
        )

    if not risk_response.data:
        raise HTTPException(
            status_code=400,
            detail="Risk parameters must be configured before starting the simulation"
        )

    return {
        **config_response.data[0],
        "risk": risk_response.data[0]
    }

STRATEGY_FUNCTIONS = {
    "SMA": sma_evaluate,
}

def start_simulation(configuration_id: str, user_id: str) -> dict:
    """Validates the full configuration exists and creates a new simulation run."""
    simulation_configuration = get_full_configuration(configuration_id, user_id)
    processed_data = process_historical_data(
        asset=simulation_configuration["asset"],
        start_date=date.fromisoformat(simulation_configuration["start_date"]),
        end_date=date.fromisoformat(simulation_configuration["end_date"])
    )

    strategy_function = STRATEGY_FUNCTIONS[simulation_configuration["strategy"]]
    decisions = run_strategy(candles=processed_data.candles, strategy_function=strategy_function)

    prices_by_date = {c.date: c.close for c in processed_data.candles}

    simulation_data = {
        "configuration_id": configuration_id,
        "user_id": user_id,
        "status": "RUNNING"
    }

    try:
        saved = (
            supabase
            .table("simulations")
            .insert(simulation_data)
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the database, please try again"
        )

    if not saved.data:
        raise HTTPException(
            status_code=500,
            detail="Could not start the simulation"
        )

    simulation_id = saved.data[0]["id"]

    trades = run_portfolio(
        candles=processed_data.candles,
        decisions=decisions,
        initial_capital=simulation_configuration["initial_capital"]
    )
    executed_dates = {t.date for t in trades}

    save_decisions(simulation_id, decisions, executed_dates, prices_by_date)
    save_trades(simulation_id, trades)

    try:
        updated = (
            supabase
            .table("simulations")
            .update({
                "status": "FINISHED",
                "finished_at": datetime.now(timezone.utc).isoformat()
            })
            .eq("id", simulation_id)
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not finalize the simulation status"
        )

    if not updated.data:
        raise HTTPException(
            status_code=500,
            detail="Could not finalize the simulation status"
        )

    return updated.data[0]


def get_simulation_status(simulation_id: str, user_id: str) -> dict:
    if not is_valid_uuid(simulation_id):
        raise HTTPException(
            status_code=404,
            detail="Simulation not found"
        )

    try:
        response = (
            supabase
            .table("simulations")
            .select("*")
            .eq("id", simulation_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the database, please try again"
        )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Simulation not found"
        )

    return response.data[0]