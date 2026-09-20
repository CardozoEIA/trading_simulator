from datetime import date, datetime, timezone

from fastapi import HTTPException

from app.services.historical_data.processor import process_historical_data
from app.services.strategy.engine import run_strategy
from app.services.strategy.strategies.sma import evaluate as sma_evaluate
from app.services.strategy.strategies.rsi import evaluate as rsi_evaluate
from app.services.strategy.strategies.bollinger import evaluate as bollinger_evaluate
from app.services.strategy.strategies.momentum import evaluate as momentum_evaluate
from app.services.strategy.schema import DecisionAction

from app.core.supabase import supabase_admin as supabase
from app.core.validation import is_valid_uuid
from app.modules.portfolio.service import run_portfolio, save_trades, save_equity_curve
from app.modules.decisions.service import save_decisions
from app.modules.risk.manager import RiskManager
from app.services.indicators.calculator import calculate_all
from app.modules.signals.service import save_signals


def get_full_configuration(configuration_id: str, user_id: str) -> dict:
    """Joins backtest_configurations + risk_configurations for a given configuration."""
    if not is_valid_uuid(configuration_id):
        raise HTTPException(status_code=404, detail="The referenced simulation configuration was not found")

    try:
        config_response = (
            supabase.table("backtest_configurations").select("*")
            .eq("id", configuration_id).eq("user_id", user_id).limit(1).execute()
        )
    except Exception:
        raise HTTPException(status_code=503, detail="Could not connect to the database, please try again")

    if not config_response.data:
        raise HTTPException(status_code=404, detail="The referenced simulation configuration was not found")

    try:
        risk_response = (
            supabase.table("risk_configurations").select("*")
            .eq("configuration_id", configuration_id).eq("user_id", user_id).limit(1).execute()
        )
    except Exception:
        raise HTTPException(status_code=503, detail="Could not connect to the database, please try again")

    if not risk_response.data:
        raise HTTPException(status_code=400, detail="Risk parameters must be configured before starting the simulation")

    return {**config_response.data[0], "risk": risk_response.data[0]}


STRATEGY_FUNCTIONS = {
    "SMA": sma_evaluate,
    "RSI": rsi_evaluate,
    "BOLLINGER": bollinger_evaluate,
    "MOMENTUM": momentum_evaluate,
}


def start_simulation(configuration_id: str, user_id: str) -> dict:
    """Validates the full configuration exists and creates a new simulation run."""
    simulation_configuration = get_full_configuration(configuration_id, user_id)
    processed_data = process_historical_data(
        asset=simulation_configuration["asset"],
        start_date=date.fromisoformat(simulation_configuration["start_date"]),
        end_date=date.fromisoformat(simulation_configuration["end_date"]),
    )

    selected_functions = [
        STRATEGY_FUNCTIONS[s] for s in simulation_configuration["strategies"]
    ]
    decisions = run_strategy(
        candles=processed_data.candles, strategy_functions=selected_functions
    )
    signal_snapshots = calculate_all(processed_data.candles)

    prices_by_date = {c.date: c.close for c in processed_data.candles}

    risk_manager = RiskManager(
        stop_loss_percentage=simulation_configuration["risk"]["stop_loss_percentage"],
        max_position_size=simulation_configuration["risk"]["max_position_size"],
        max_drawdown=simulation_configuration["risk"]["max_drawdown"]
    )

    simulation_data = {
        "configuration_id": configuration_id,
        "user_id": user_id,
        "status": "RUNNING",
    }

    try:
        saved = supabase.table("simulations").insert(simulation_data).execute()
    except Exception:
        raise HTTPException(status_code=503, detail="Could not connect to the database, please try again")

    if not saved.data:
        raise HTTPException(status_code=500, detail="Could not start the simulation")

    simulation_id = saved.data[0]["id"]

    # CAMBIO 1: ahora se desempaquetan 4 valores, no 3 (se agrega `overrides`)
    trades, equity_curve, rejections, overrides = run_portfolio(
        candles=processed_data.candles,
        decisions=decisions,
        initial_capital=simulation_configuration["initial_capital"],
        risk_manager=risk_manager
    )
    executed_dates = {t.date for t in trades}

    # CAMBIO 2: se pasa `overrides` como sexto argumento
    save_decisions(simulation_id, decisions, executed_dates, prices_by_date, rejections, overrides)
    save_trades(simulation_id, trades)
    save_equity_curve(simulation_id, equity_curve)
    save_signals(simulation_id, signal_snapshots)

    try:
        updated = (
            supabase.table("simulations")
            .update({"status": "FINISHED", "finished_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", simulation_id).execute()
        )
    except Exception:
        raise HTTPException(status_code=503, detail="Could not finalize the simulation status")

    if not updated.data:
        raise HTTPException(status_code=500, detail="Could not finalize the simulation status")

    return updated.data[0]


def get_simulation_status(simulation_id: str, user_id: str) -> dict:
    if not is_valid_uuid(simulation_id):
        raise HTTPException(status_code=404, detail="Simulation not found")

    try:
        response = (
            supabase.table("simulations").select("*")
            .eq("id", simulation_id).eq("user_id", user_id).limit(1).execute()
        )
    except Exception:
        raise HTTPException(status_code=503, detail="Could not connect to the database, please try again")

    if not response.data:
        raise HTTPException(status_code=404, detail="Simulation not found")

    return response.data[0]
