from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


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
    strategies: list[StrategyType] = Field(default_factory=list)
    # US-21: custom strategies of the student (ids from /custom-strategies) to run next to, or instead of, the built-in ones
    custom_strategy_ids: list[str] = Field(default_factory=list)
    # US-24: with two or more strategies, the score the blended signal must pass to trigger BUY/SELL. Empty = 0.1
    ensemble_threshold: float | None = None


class BacktestConfigurationResponse(BaseModel):
    id: str
    asset: str
    start_date: date
    end_date: date
    initial_capital: float
    strategies: list[str]
    ensemble_threshold: float | None = None
    data_available: bool
    records: int