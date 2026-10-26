from datetime import date, datetime, timezone

from fastapi import HTTPException

from app.services.historical_data.processor import process_historical_data
from app.services.strategy.engine import run_strategy
from app.services.strategy.strategies.sma import evaluate as sma_evaluate
from app.services.strategy.strategies.rsi import evaluate as rsi_evaluate
from app.services.strategy.strategies.bollinger import evaluate as bollinger_evaluate
from app.services.strategy.strategies.momentum import evaluate as momentum_evaluate
from app.services.strategy.schema import DecisionAction
from app.services.benchmark.calculator import calculate_buy_and_hold

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
        raise HTTPException(
            status_code=404,
            detail="The referenced simulation configuration was not found",
        )

    try:
        config_response = (
            supabase.table("backtest_configurations")
            .select("*")
            .eq("id", configuration_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the database, please try again",
        )

    if not config_response.data:
        raise HTTPException(
            status_code=404,
            detail="The referenced simulation configuration was not found",
        )

    try:
        risk_response = (
            supabase.table("risk_configurations")
            .select("*")
            .eq("configuration_id", configuration_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the database, please try again",
        )

    if not risk_response.data:
        raise HTTPException(
            status_code=400,
            detail="Risk parameters must be configured before starting the simulation",
        )

    return {**config_response.data[0], "risk": risk_response.data[0]}


def build_configuration_summary(configuration_id: str, user_id: str) -> dict:
    """Assembles the configuration summary, including the buy & hold benchmark."""
    simulation_configuration = get_full_configuration(configuration_id, user_id)

    # fill in: convert start_date/end_date strings to date objects,
    # exactly like start_simulation already does with date.fromisoformat(...)
    start_date = date.fromisoformat(simulation_configuration["start_date"])
    end_date = date.fromisoformat(simulation_configuration["end_date"])

    # fill in: call process_historical_data(asset=..., start_date=..., end_date=...)
    processed_data = process_historical_data(
        asset=simulation_configuration["asset"],
        start_date=start_date,
        end_date=end_date)

    # fill in: call calculate_buy_and_hold(candles=..., initial_capital=...)
    benchmark = calculate_buy_and_hold(
        candles=processed_data.candles,
        initial_capital=simulation_configuration["initial_capital"]
    )

    # fill in: return simulation_configuration merged with the new "benchmark" key
    return {
        **simulation_configuration,
        "benchmark": benchmark.model_dump()
    }

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
        max_drawdown=simulation_configuration["risk"]["max_drawdown"],
    )

    simulation_data = {
        "configuration_id": configuration_id,
        "user_id": user_id,
        "status": "RUNNING",
    }

    try:
        saved = supabase.table("simulations").insert(simulation_data).execute()
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the database, please try again",
        )

    if not saved.data:
        raise HTTPException(status_code=500, detail="Could not start the simulation")

    simulation_id = saved.data[0]["id"]

    trades, equity_curve, rejections, overrides, stop_reason = run_portfolio(
        candles=processed_data.candles,
        decisions=decisions,
        initial_capital=simulation_configuration["initial_capital"],
        risk_manager=risk_manager,
    )

    processed_days = len(equity_curve)

    decisions = decisions[:processed_days]
    signal_snapshots = signal_snapshots[:processed_days]

    executed_dates = {t.date for t in trades}

    save_decisions(
        simulation_id, decisions, executed_dates, prices_by_date, rejections, overrides
    )
    save_trades(simulation_id, trades)
    save_equity_curve(simulation_id, equity_curve)
    save_signals(simulation_id, signal_snapshots)

    try:
        updated = (
            supabase.table("simulations")
            .update(
                {
                    "status": "STOPPED_BY_RISK" if stop_reason else "FINISHED",
                    "stop_reason": stop_reason,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .eq("id", simulation_id)
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=503, detail="Could not finalize the simulation status"
        )

    if not updated.data:
        raise HTTPException(
            status_code=500, detail="Could not finalize the simulation status"
        )

    return updated.data[0]


def get_simulation_status(simulation_id: str, user_id: str) -> dict:
    if not is_valid_uuid(simulation_id):
        raise HTTPException(status_code=404, detail="Simulation not found")

    try:
        response = (
            supabase.table("simulations")
            .select("*")
            .eq("id", simulation_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the database, please try again",
        )

    if not response.data:
        raise HTTPException(status_code=404, detail="Simulation not found")

    return response.data[0]

HISTORY_LIMIT = 50


def get_simulation_history(user_id: str) -> list[dict]:
    """Lists the user's simulations, newest first, with configuration and final performance.
    Uses three queries in total instead of one per simulation."""
    try:
        sims = (
            supabase.table("simulations")
            .select("id, configuration_id, status, started_at, finished_at, stop_reason")
            .eq("user_id", user_id)
            .order("started_at", desc=True)
            .limit(HISTORY_LIMIT)
            .execute()
        ).data

        if not sims:
            return []

        config_ids = list({s["configuration_id"] for s in sims})
        sim_ids = [s["id"] for s in sims]

        configs = (
            supabase.table("backtest_configurations")
            .select("id, asset, start_date, end_date, initial_capital, strategies")
            .in_("id", config_ids)
            .execute()
        ).data

        finals = (
            supabase.table("simulation_final_values")
            .select("simulation_id, portfolio_value")
            .in_("simulation_id", sim_ids)
            .execute()
        ).data
    except Exception:
        raise HTTPException(status_code=503, detail="Could not connect to the database, please try again")

    configs_by_id = {c["id"]: c for c in configs}
    final_by_sim = {f["simulation_id"]: f["portfolio_value"] for f in finals}

    history = []
    for s in sims:
        config = configs_by_id.get(s["configuration_id"])
        if not config:
            continue  # orphan simulation without configuration; skip instead of failing the whole list

        initial_capital = config["initial_capital"]
        final_value = final_by_sim.get(s["id"])
        total_return_pct = (
            ((final_value / initial_capital) - 1) * 100
            if final_value is not None and initial_capital > 0
            else None
        )

        history.append({
            "id": s["id"],
            "status": s["status"],
            "started_at": s["started_at"],
            "finished_at": s["finished_at"],
            "stop_reason": s["stop_reason"],
            "asset": config["asset"],
            "start_date": config["start_date"],
            "end_date": config["end_date"],
            "strategies": config["strategies"],
            "initial_capital": initial_capital,
            "final_value": final_value,
            "total_return_pct": total_return_pct,
        })

    return history


# Rows that belong to one simulation, deleted before the simulation itself.
# (simulation_final_values is a view over the equity curve: nothing to delete there.)
SIMULATION_CHILD_TABLES = (
    "simulation_decisions",
    "simulation_trades",
    "simulation_equity_curve",
    "simulation_signals",
    "simulation_insights",
    "chat_messages",
)


def delete_simulation(simulation_id: str, user_id: str) -> None:
    """Deletes one of the student's simulations and everything recorded for it.

    Its configuration is deleted too when no other simulation uses it. Children go first,
    so a failure halfway leaves the simulation in the history and deleting again finishes it.
    """
    simulation = get_simulation_status(simulation_id, user_id)  # 404 when missing or not owned
    if simulation["status"] == "RUNNING":
        raise HTTPException(status_code=409, detail="The simulation is still running")

    configuration_id = simulation["configuration_id"]
    try:
        for table in SIMULATION_CHILD_TABLES:
            supabase.table(table).delete().eq("simulation_id", simulation_id).execute()
        supabase.table("simulations").delete().eq("id", simulation_id).eq("user_id", user_id).execute()

        still_used = (
            supabase.table("simulations").select("id")
            .eq("configuration_id", configuration_id).limit(1).execute()
        ).data
        if not still_used:
            supabase.table("risk_configurations").delete() \
                .eq("configuration_id", configuration_id).eq("user_id", user_id).execute()
            supabase.table("backtest_configurations").delete() \
                .eq("id", configuration_id).eq("user_id", user_id).execute()
    except Exception:
        raise HTTPException(status_code=503, detail="Could not connect to the database, please try again")
