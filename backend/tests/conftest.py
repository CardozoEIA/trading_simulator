# tests/conftest.py
import pytest


@pytest.fixture(autouse=True)
def no_tracing(monkeypatch):
    """Tests never contact Langfuse, even if backend/.env has tracing keys."""
    for name in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
