# app/modules/agent/schema.py
from pydantic import BaseModel

class ExplainRequest(BaseModel):
    date: str

class ExplainResponse(BaseModel):
    explanation: str