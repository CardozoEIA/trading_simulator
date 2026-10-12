from pydantic import BaseModel

from app.modules.simulations.schema import SimulationStatus


class SimulationResultsSummary(BaseModel):
    simulation_id: str
    status: SimulationStatus
    initial_capital: float
    final_capital: float
    profit_loss: float
    total_return_pct: float

class SimulationMetrics(BaseModel):
    simulation_id: str
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    profit_factor: float | None  # None when there are no losing trades
    total_trades: int        # number of completed round-trips (BUY→SELL)
    winning_trades: int