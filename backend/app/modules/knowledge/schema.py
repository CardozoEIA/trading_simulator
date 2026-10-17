from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)


class SourceOut(BaseModel):
    document_id: str
    filename: str
    page: int | None = None
    chunk_index: int
    similarity: float
    snippet: str


class AskResponse(BaseModel):
    answer: str
    refused: bool
    sources: list[SourceOut] = Field(default_factory=list)


class HistoryMessage(BaseModel):
    role: str
    content: str
    refused: bool = False
    sources: list[SourceOut] = Field(default_factory=list)


class HistoryResponse(BaseModel):
    messages: list[HistoryMessage]
