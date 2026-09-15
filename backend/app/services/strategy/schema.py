from datetime import date
from enum import Enum

from pydantic import BaseModel


class DecisionAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class StrategySignal(BaseModel):
    direction: DecisionAction
    score: float  # -1.0 (strong SELL) to +1.0 (strong BUY)
    reasoning: str


class Decision(BaseModel):
    date: date
    action: DecisionAction
    reason: str