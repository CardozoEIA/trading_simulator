from fastapi import HTTPException

from app.core.supabase import supabase_admin as supabase
from app.core.validation import is_valid_uuid
from app.modules.results.schema import SimulationResultsSummary
import math
from app.modules.results.schema import SimulationMetrics

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
def get_metrics(simulation_id: str, user_id: str) -> SimulationMetrics:
    if not is_valid_uuid(simulation_id):
        raise HTTPException(status_code=404, detail="Simulation not found")

    # ownership + initial capital (same pattern as get_results_summary)
    try:
        sim = (
            supabase.table("simulations").select("configuration_id")
            .eq("id", simulation_id).eq("user_id", user_id).limit(1).execute()
        )
    except Exception:
        raise HTTPException(status_code=503, detail="Could not connect to the database, please try again")
    if not sim.data:
        raise HTTPException(status_code=404, detail="Simulation not found")

    try:
        config = (
            supabase.table("backtest_configurations").select("initial_capital")
            .eq("id", sim.data[0]["configuration_id"]).limit(1).execute()
        )
    except Exception:
        raise HTTPException(status_code=503, detail="Could not connect to the database, please try again")
    if not config.data:
        raise HTTPException(status_code=404, detail="Simulation configuration not found")
    initial_capital = config.data[0]["initial_capital"]
    if initial_capital <= 0:
        raise HTTPException(status_code=500, detail="Invalid configuration: initial capital must be greater than zero")

    # equity curve (chronological) for return, Sharpe and max drawdown
    equity = (
        supabase.table("simulation_equity_curve")
        .select("date, portfolio_value")
        .eq("simulation_id", simulation_id).order("date").execute()
    ).data
    values = [row["portfolio_value"] for row in equity]

    total_return_pct = ((values[-1] / initial_capital) - 1) * 100 if values else 0.0

    # Sharpe ratio: annualized, from daily returns (risk-free rate assumed 0 for the MVP)
    sharpe_ratio = 0.0
    if len(values) > 1:
        daily_returns = [(values[i] / values[i - 1]) - 1 for i in range(1, len(values)) if values[i - 1] > 0]
        if len(daily_returns) > 1:
            mean = sum(daily_returns) / len(daily_returns)
            variance = sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            std = math.sqrt(variance)
            if std > 0:
                sharpe_ratio = (mean / std) * math.sqrt(252)

    # Max drawdown: largest peak-to-trough decline over the equity curve
    max_drawdown_pct = 0.0
    peak = values[0] if values else initial_capital
    for v in values:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > max_drawdown_pct:
                max_drawdown_pct = dd
    max_drawdown_pct *= 100

    # Win rate & profit factor: from completed round-trips (BUY followed by SELL)
    trades = (
        supabase.table("simulation_trades")
        .select("type, price, quantity, date")
        .eq("simulation_id", simulation_id).order("date").execute()
    ).data

    pnls = []
    i = 0
    while i + 1 < len(trades):
        entry, exit_ = trades[i], trades[i + 1]
        if entry["type"] == "BUY" and exit_["type"] == "SELL":
            pnls.append((exit_["price"] - entry["price"]) * entry["quantity"])
            i += 2
        else:
            i += 1

    total_trades = len(pnls)
    winning_trades = len([p for p in pnls if p > 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = abs(sum(p for p in pnls if p < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else None

    return SimulationMetrics(
        simulation_id=simulation_id,
        total_return_pct=total_return_pct,
        sharpe_ratio=sharpe_ratio,
        max_drawdown_pct=max_drawdown_pct,
        win_rate=win_rate,
        profit_factor=profit_factor,
        total_trades=total_trades,
        winning_trades=winning_trades,
    )