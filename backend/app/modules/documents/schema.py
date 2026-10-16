from pydantic import BaseModel


class DocumentOut(BaseModel):
    # TODO(Lucas): declare the fields returned by the API, same names as the table columns:
    # id, filename, file_type, size_bytes, status, chunk_count, error (optional), created_at.
    # Look at app/modules/chat/schema.py for the style (optional = `str | None = None`).
    pass
