# app/modules/insights/schema.py
from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class InsightsStatus(str, Enum):
    NOT_GENERATED = "NOT_GENERATED"
    PENDING = "PENDING"
    READY = "READY"
    FAILED = "FAILED"


class Insight(BaseModel):
    title: str
    detail: str


class SimulationInsightsResponse(BaseModel):
    simulation_id: str
    status: InsightsStatus
    insights: list[Insight] = []
    error: str | None = None
    generated_at: datetime | None = None
