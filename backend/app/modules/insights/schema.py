# app/modules/insights/schema.py
from enum import Enum
from typing import Literal

from pydantic import BaseModel


class InsightsStatus(str, Enum):
    PENDING = "PENDING"    # the agent is still writing the explanations
    READY = "READY"
    FAILED = "FAILED"      # highlights are shown with their facts, without the agent's text


class Highlight(BaseModel):
    kind: Literal["BUY_AND_HOLD", "RISK_STOP", "BEST_TRADE", "WORST_TRADE", "MAX_DRAWDOWN"]
    label: str
    tone: Literal["positive", "negative", "neutral"]
    dates: list[str]
    facts: str
    title: str | None = None         # agent explanation (None until it is ready)
    explanation: str | None = None


class SimulationInsightsResponse(BaseModel):
    simulation_id: str
    status: InsightsStatus
    highlights: list[Highlight]
    error: str | None = None
