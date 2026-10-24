# app/modules/report/schema.py
from typing import Literal

from pydantic import BaseModel


class ReportRow(BaseModel):
    label: str
    value: str


class ReportTable(BaseModel):
    columns: list[str]
    rows: list[list[str]]


class ReportSection(BaseModel):
    key: Literal["setup", "performance", "key_decisions", "benchmark", "disclaimer"]
    title: str
    narrative: str | None = None   # agent text (verified); None when it could not be backed by the data
    rows: list[ReportRow]
    table: ReportTable | None = None
    note: str | None = None


class SimulationReportResponse(BaseModel):
    simulation_id: str
    title: str
    generated_at: str
    markdown: str
    sections: list[ReportSection]
