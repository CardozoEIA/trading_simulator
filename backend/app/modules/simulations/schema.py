from datetime import datetime, date
from enum import Enum

from pydantic import BaseModel

from app.services.benchmark.schema import BuyAndHoldSummary


class SimulationStatus(str, Enum):
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    STOPPED_BY_RISK = "STOPPED_BY_RISK"


class SimulationStartRequest(BaseModel):
    configuration_id: str


class SimulationResponse(BaseModel):
    id: str
    configuration_id: str
    status: SimulationStatus
    started_at: datetime
    finished_at: datetime | None = None
    stop_reason: str | None = None


class RiskSummary(BaseModel):
    stop_loss_percentage: float
    max_position_size: float
    max_drawdown: float


class ConfigurationSummaryResponse(BaseModel):
    id: str
    asset: str
    start_date: date
    end_date: date
    initial_capital: float
    strategies: list[str]
    risk: RiskSummary
    benchmark: BuyAndHoldSummary
class SimulationHistoryItem(BaseModel):
    id: str
    status: SimulationStatus
    started_at: datetime
    finished_at: datetime | None = None
    stop_reason: str | None = None
    asset: str
    start_date: date
    end_date: date
    strategies: list[str]
    initial_capital: float
    final_value: float | None = None       # None while the simulation is still running
    total_return_pct: float | None = None