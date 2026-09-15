from datetime import date
from enum import Enum

from pydantic import BaseModel


class StrategyType(str, Enum):
    SMA = "SMA"
    RSI = "RSI"
    BOLLINGER = "BOLLINGER"
    MOMENTUM = "MOMENTUM"


class BacktestConfiguration(BaseModel):
    asset: str
    start_date: date
    end_date: date
    initial_capital: float
    strategies: list[StrategyType]


class BacktestConfigurationResponse(BaseModel):
    id: str
    asset: str
    start_date: date
    end_date: date
    initial_capital: float
    strategies: list[str]
    data_available: bool
    records: int