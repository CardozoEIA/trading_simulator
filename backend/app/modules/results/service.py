from fastapi import HTTPException

from app.core.supabase import supabase_admin as supabase
from app.core.validation import is_valid_uuid
from app.modules.results.schema import SimulationResultsSummary


def get_results_summary(simulation_id: str, user_id: str) -> SimulationResultsSummary:

    if not is_valid_uuid(simulation_id):
        raise HTTPException(status_code=404, detail="Simulation not found")

    try:
        simulation_response = (
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

    if not simulation_response.data:
        raise HTTPException(status_code=404, detail="Simulation not found")

    simulation = simulation_response.data[0]

    try:
        configuration_response = (
            supabase.table("backtest_configurations")
            .select("initial_capital")
            .eq("id", simulation["configuration_id"])
            .limit(1)
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the database, please try again",
        )

    if not configuration_response.data:
        raise HTTPException(
            status_code=404, detail="Simulation configuration not found"
        )

    initial_capital = configuration_response.data[0]["initial_capital"]
    if initial_capital <= 0:
        raise HTTPException(
            status_code=500,
            detail="Invalid configuration: initial capital must be greater than zero",
        )

    try:
        equity_response = (
            supabase.table("simulation_equity_curve")
            .select("*")
            .eq("simulation_id", simulation_id)
            .order("date", desc=True)
            .limit(1)
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the database, please try again",
        )

    if not equity_response.data:
        raise HTTPException(
            status_code=404, detail="No equity curve data found for this simulation"
        )

    final_capital = equity_response.data[0]["portfolio_value"]

    profit_loss = final_capital - initial_capital
    total_return_pct = (profit_loss / initial_capital) * 100

    return SimulationResultsSummary(
        simulation_id=simulation_id,
        status=simulation["status"],
        initial_capital=initial_capital,
        final_capital=final_capital,
        profit_loss=profit_loss,
        total_return_pct=total_return_pct,
    )
