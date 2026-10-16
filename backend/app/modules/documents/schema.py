from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: str
    filename: str
    file_type: str
    size_bytes: int
    status: str
    chunk_count: int
    error: str | None = None
    created_at: str