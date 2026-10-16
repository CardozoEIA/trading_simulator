from typing import TypedDict


class KnowledgeState(TypedDict, total=False):
    question: str
    user_id: str
    intent: str          # "question" | "greeting" | "invalid"
    chunks: list[dict]   # retrieved passages, best first (see vectorstore.repository.search_chunks)
    sufficient: bool     # did the retrieved passages pass the sufficiency check?
    answer: str
    refused: bool        # True when the agent declined to answer
    sources: list[dict]  # passages the answer is based on
