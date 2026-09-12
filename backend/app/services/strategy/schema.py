from datetime import date
from enum import Enum

from pydantic import BaseModel


class DecisionAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Decision(BaseModel):
    date: date
    action: DecisionAction
    reason: str