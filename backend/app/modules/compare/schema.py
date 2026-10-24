# app/modules/compare/schema.py
from typing import Literal

from pydantic import BaseModel, Field


class CompareRequest(BaseModel):
    simulation_a: str = Field(min_length=1)
    simulation_b: str = Field(min_length=1)


class ComparedSimulation(BaseModel):
    id: str
    label: str
    status: str
    started_at: str | None = None


class ConfigurationDifference(BaseModel):
    field: str
    label: str
    a: str
    b: str
    changed: bool


class MetricDifference(BaseModel):
    metric: str
    label: str
    a: float | None = None
    b: float | None = None
    delta: float | None = None          # B minus A
    a_display: str
    b_display: str
    delta_display: str
    better: Literal["a", "b", "tie"] | None = None


class CompareResponse(BaseModel):
    simulation_a: ComparedSimulation
    simulation_b: ComparedSimulation
    configuration_diff: list[ConfigurationDifference]
    metrics_diff: list[MetricDifference]
    winner: Literal["a", "b", "tie"]
    explanation: str | None = None      # None when the agent could not back its text with the data
