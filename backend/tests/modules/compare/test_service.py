# tests/modules/compare/test_service.py
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user
from app.modules.compare import routes, service
from tests.agents.compare.test_compare import GOOD, ScriptedLLM, fake_tools  # noqa: F401 (fixture)


def test_compare_returns_both_runs_diffs_and_explanation(fake_tools):
    result = service.compare_simulations("sim-a", "sim-b", "user-1", llm=ScriptedLLM([GOOD]))
    assert result["simulation_a"]["label"] == "SPY · SMA · 2023-01-02 to 2023-06-30"
    assert result["simulation_b"]["status"] == "STOPPED_BY_RISK"
    assert result["winner"] == "a"
    assert result["explanation"] == GOOD
    assert {m["metric"] for m in result["metrics_diff"]} >= {"total_return_pct", "sharpe_ratio", "win_rate"}


def test_same_simulation_twice_is_400():
    with pytest.raises(HTTPException) as exc:
        service.compare_simulations("sim-a", "sim-a", "user-1", llm=ScriptedLLM([]))
    assert exc.value.status_code == 400


def test_ollama_down_returns_503(fake_tools):
    class Down:
        def invoke(self, _messages):
            raise ConnectionError("connection refused")

    with pytest.raises(HTTPException) as exc:
        service.compare_simulations("sim-a", "sim-b", "user-1", llm=Down())
    assert exc.value.status_code == 503
    assert "Ollama" in exc.value.detail


# --- endpoint ---

@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="user-1")
    return TestClient(app)


def test_foreign_simulation_returns_404(client, monkeypatch):
    def deny(simulation_a, simulation_b, user_id):
        raise HTTPException(status_code=404, detail="Simulation not found")

    monkeypatch.setattr(routes, "compare_simulations", deny)
    response = client.post("/simulations/compare", json={"simulation_a": "sim-a", "simulation_b": "foreign"})
    assert response.status_code == 404


def test_endpoint_validates_body_and_returns_the_response_model(client, fake_tools, monkeypatch):
    assert client.post("/simulations/compare", json={"simulation_a": "sim-a"}).status_code == 422

    monkeypatch.setattr(
        routes, "compare_simulations",
        lambda a, b, user_id: service.compare_simulations(a, b, user_id, llm=ScriptedLLM([GOOD])),
    )
    response = client.post("/simulations/compare", json={"simulation_a": "sim-a", "simulation_b": "sim-b"})
    assert response.status_code == 200
    body = response.json()
    assert body["winner"] == "a"
    profit_factor = next(m for m in body["metrics_diff"] if m["metric"] == "profit_factor")
    assert profit_factor["b_display"] == "No losing trades"
