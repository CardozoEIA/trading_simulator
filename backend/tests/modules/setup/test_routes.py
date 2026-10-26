# tests/modules/setup/test_routes.py
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user
from app.modules.setup import routes, service
from tests.agents.setup.test_setup import COMPLETE, COMPLETE_EXTRACTION, ScriptedLLM, TODAY, database  # noqa: F401


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="user-1")
    return TestClient(app)


def test_body_is_validated(client):
    assert client.post("/simulations/setup/parse", json={"description": ""}).status_code == 422
    assert client.post("/simulations/setup/parse", json={"description": "x" * 1501}).status_code == 422


def test_endpoint_returns_the_proposal(client, database, monkeypatch):
    monkeypatch.setattr(
        routes, "parse_setup",
        lambda description, user_id=None: service.parse_setup(
            description, user_id=user_id, llm=ScriptedLLM(COMPLETE_EXTRACTION), today=TODAY),
    )
    response = client.post("/simulations/setup/parse", json={"description": COMPLETE})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert body["proposal"]["strategies"] == ["SMA", "RSI"]


def test_ollama_down_returns_503(database):
    class Down:
        def invoke(self, _messages):
            raise ConnectionError("connection refused")

    with pytest.raises(HTTPException) as exc:
        service.parse_setup(COMPLETE, llm=Down(), today=TODAY)
    assert exc.value.status_code == 503
    assert "Ollama" in exc.value.detail
