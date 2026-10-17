"""Local chat model shared by the agents (Ollama)."""
from langchain_ollama import ChatOllama

MODEL_NAME = "qwen2.5:7b"
OLLAMA_TIMEOUT_SECONDS = 60


def get_chat_model(**kwargs) -> ChatOllama:
    """Deterministic (temperature 0) local model. A slow Ollama fails after the timeout instead of hanging."""
    return ChatOllama(
        model=MODEL_NAME,
        temperature=0,
        client_kwargs={"timeout": OLLAMA_TIMEOUT_SECONDS},
        **kwargs,
    )
