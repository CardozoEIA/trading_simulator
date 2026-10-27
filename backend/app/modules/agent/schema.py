# app/modules/agent/schema.py
from datetime import datetime

from pydantic import BaseModel, Field


class ExplainRequest(BaseModel):
    date: str


class ToolCall(BaseModel):
    tool: str
    arguments: dict = Field(default_factory=dict)
    result: str | None = None


class RemovedStatement(BaseModel):
    statement: str
    problems: list[str] = Field(default_factory=list)


class Verification(BaseModel):
    verified: bool
    tools_called: int = 0
    removed: list[RemovedStatement] = Field(default_factory=list)


class ExplainResponse(BaseModel):
    explanation: str
    trace: list[ToolCall] = Field(default_factory=list)       # US-31: tools called and the values they returned
    verification: Verification | None = None                  # US-31: what the self-check found


class TraceRecord(BaseModel):
    id: int
    source: str
    date: str | None = None
    answer: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    verification: Verification | None = None
    created_at: datetime
