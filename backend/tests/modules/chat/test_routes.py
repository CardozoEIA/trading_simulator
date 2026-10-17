from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user
from app.modules.chat import routes


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="user-1")
    return TestClient(app)


def test_chat_endpoint_validates_the_body(client):
    assert client.post("/simulations/sim-1/chat", json={"message": ""}).status_code == 422
    assert client.post("/simulations/sim-1/chat", json={"message": "x" * 501}).status_code == 422


def test_chat_endpoint_returns_the_response_model(client, monkeypatch):
    monkeypatch.setattr(
        routes,
        "chat",
        lambda **kwargs: {
            "reply": "ok",
            "route": "propose_change",
            "date": None,
            "suggestions": ["a", "b", "c"],
            "proposed_change": {"parameter": "max_drawdown", "label": "max drawdown", "current": None, "suggested": 10.0},
        },
    )

    response = client.post("/simulations/sim-1/chat", json={"message": "hi"})

    assert response.status_code == 200
    assert response.json()["proposed_change"]["suggested"] == 10.0


def test_stream_endpoint_uses_server_sent_events(client, monkeypatch):
    monkeypatch.setattr(
        routes,
        "chat_stream",
        lambda **kwargs: iter(['event: token\ndata: {"text": "Hi"}\n\n', 'event: done\ndata: {"reply": "Hi"}\n\n']),
    )

    response = client.post("/simulations/sim-1/chat/stream", json={"message": "hi"})

    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: token" in response.text and "event: done" in response.text


def test_stream_endpoint_returns_404_for_a_foreign_simulation(client, monkeypatch):
    def deny(**kwargs):
        raise HTTPException(status_code=404, detail="Simulation not found")

    monkeypatch.setattr(routes, "chat_stream", deny)

    assert client.post("/simulations/sim-1/chat/stream", json={"message": "hi"}).status_code == 404


def test_history_and_delete_endpoints(client, monkeypatch):
    monkeypatch.setattr(
        routes,
        "get_history",
        lambda simulation_id, user_id: {"messages": [{"role": "user", "content": "q"}], "suggestions": ["a"]},
    )
    deleted = []
    monkeypatch.setattr(routes, "reset_conversation", lambda simulation_id, user_id: deleted.append(simulation_id))

    history = client.get("/simulations/sim-1/chat/history")
    cleared = client.delete("/simulations/sim-1/chat")

    assert history.json()["messages"][0]["content"] == "q"
    assert cleared.status_code == 204
    assert deleted == ["sim-1"]