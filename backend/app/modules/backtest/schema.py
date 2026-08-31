from datetime import date
from enum import Enum

from pydantic import BaseModel


class StrategyType(str, Enum):
    SMA = "SMA"
    RSI = "RSI"
    BOLLINGER = "BOLLINGER"


class BacktestConfiguration(BaseModel):
    asset: str
    start_date: date
    end_date: date
    initial_capital: float
    strategy: StrategyType


class BacktestConfigurationResponse(BaseModel):
    id: str
    asset: str
    start_date: date
    end_date: date
    initial_capital: float
    strategy: str
    data_available: bool
    records: int