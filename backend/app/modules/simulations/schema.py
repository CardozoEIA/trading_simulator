from datetime import datetime, date
from enum import Enum

from pydantic import BaseModel


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
    strategy: str
    risk: RiskSummary