from pydantic import BaseModel

from app.modules.simulations.schema import SimulationStatus


class SimulationResultsSummary(BaseModel):
    simulation_id: str
    status: SimulationStatus
    initial_capital: float
    final_capital: float
    profit_loss: float
    total_return_pct: float