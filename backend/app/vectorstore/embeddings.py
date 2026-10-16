"""Embedding model shared by document ingestion and retrieval.

Documents and questions MUST be embedded with the same model, otherwise the vectors live in
different spaces and similarity search returns noise.
"""
from functools import lru_cache

from langchain_ollama import OllamaEmbeddings

EMBEDDING_MODEL = "nomic-embed-text"
EMBEDDING_DIM = 768  # must match vector(768) in migrations/003_documents_pgvector.sql


@lru_cache(maxsize=1)
def _embedder() -> OllamaEmbeddings:
    return OllamaEmbeddings(model=EMBEDDING_MODEL, client_kwargs={"timeout": 60})


def embed_documents(texts: list[str]) -> list[list[float]]:
    """One vector per text, in the same order."""
    return _embedder().embed_documents(texts)


def embed_query(text: str) -> list[float]:
    return _embedder().embed_query(text)
