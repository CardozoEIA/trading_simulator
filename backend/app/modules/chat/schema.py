from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=500,
    )


class ProposedChange(BaseModel):
    parameter: str
    label: str
    current: float | None = None
    suggested: float


class ChatResponse(BaseModel):
    reply: str
    route: str | None = None
    date: str | None = None
    suggestions: list[str] = Field(default_factory=list)
    proposed_change: ProposedChange | None = None


class ChatHistoryMessage(BaseModel):
    role: str
    content: str
    route: str | None = None
    date: str | None = None


class ChatHistoryResponse(BaseModel):
    messages: list[ChatHistoryMessage] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)