# app/modules/whatif/schema.py
from typing import Literal

from pydantic import BaseModel

from app.modules.chat.schema import ProposedChange
from app.modules.compare.schema import CompareResponse


class WhatIfRequest(BaseModel):
    parameter: Literal["stop_loss_percentage", "max_position_size", "max_drawdown"]
    value: float


class WhatIfResponse(BaseModel):
    status: Literal["COMPLETED", "FALLBACK"]
    original_id: str
    what_if_id: str | None = None          # None when the re-run failed or was too slow
    change: ProposedChange
    comparison: CompareResponse | None = None
    fallback: str | None = None            # qualitative expected effect, no numbers
    message: str
