from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.backtest.schema import StrategyType


class CustomStrategyInput(BaseModel):
    name: str
    base_strategy: StrategyType
    params: dict[str, float] = Field(default_factory=dict)


class CustomStrategyResponse(BaseModel):
    id: str
    name: str
    base_strategy: StrategyType
    params: dict[str, float]
    created_at: datetime
    updated_at: datetime


class ValidationResponse(BaseModel):
    name: str
    base_strategy: StrategyType
    params: dict[str, float]
