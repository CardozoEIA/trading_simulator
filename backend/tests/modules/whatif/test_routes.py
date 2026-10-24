# tests/modules/whatif/test_routes.py
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user
from app.modules.whatif import routes

CHANGE = {"parameter": "stop_loss_percentage", "label": "stop-loss", "current": 5.0, "suggested": 3.0,
          "plan": ["Read", "Run", "Compare"]}


@pytest.fixture
def client(monkeypatch):
    scheduled = []
    monkeypatch.setattr(routes, "mark_pending", lambda simulation_id: scheduled.append(simulation_id))
    monkeypatch.setattr(routes, "on_simulation_finished", lambda simulation_id: None)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="user-1")
    test_client = TestClient(app)
    test_client.scheduled = scheduled
    return test_client


def test_body_is_validated(client):
    assert client.post("/simulations/sim-1/what-if", json={"parameter": "initial_capital", "value": 5}).status_code == 422
    assert client.post("/simulations/sim-1/what-if", json={"parameter": "max_drawdown"}).status_code == 422


def test_completed_what_if_schedules_insights_for_the_new_run(client, monkeypatch):
    monkeypatch.setattr(routes, "run_what_if", lambda *args: {
        "status": "COMPLETED", "original_id": "sim-1", "what_if_id": "sim-2", "change": CHANGE,
        "comparison": None, "fallback": None, "message": "done",
    })
    response = client.post("/simulations/sim-1/what-if", json={"parameter": "stop_loss_percentage", "value": 3})
    assert response.status_code == 200
    assert response.json()["what_if_id"] == "sim-2"
    assert client.scheduled == ["sim-2"]


def test_fallback_schedules_nothing(client, monkeypatch):
    monkeypatch.setattr(routes, "run_what_if", lambda *args: {
        "status": "FALLBACK", "original_id": "sim-1", "what_if_id": None, "change": CHANGE,
        "comparison": None, "fallback": "general text", "message": "too slow",
    })
    response = client.post("/simulations/sim-1/what-if", json={"parameter": "stop_loss_percentage", "value": 3})
    assert response.json()["status"] == "FALLBACK"
    assert client.scheduled == []


def test_foreign_simulation_is_404(client, monkeypatch):
    def deny(*args):
        raise HTTPException(status_code=404, detail="Simulation not found")

    monkeypatch.setattr(routes, "run_what_if", deny)
    response = client.post("/simulations/foreign/what-if", json={"parameter": "max_drawdown", "value": 10})
    assert response.status_code == 404
