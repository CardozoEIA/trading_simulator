# app/modules/setup/schema.py
from typing import Literal

from pydantic import BaseModel, Field


class SetupParseRequest(BaseModel):
    # the student's description; follow-up answers are appended to it by the client
    description: str = Field(min_length=1, max_length=1500)


class SetupProposal(BaseModel):
    asset: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    initial_capital: float | None = None
    strategies: list[str] | None = None
    stop_loss_percentage: float | None = None
    max_position_size: float | None = None
    max_drawdown: float | None = None


class SetupParseResponse(BaseModel):
    status: Literal["complete", "incomplete"]
    proposal: SetupProposal
    missing_fields: list[str]
    message: str
