# tests/modules/report/test_service.py
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.core.dependencies import get_current_user
from app.modules.report import routes, service
from tests.agents.report.test_report import DATA, GOOD


class FakeLLM:
    def __init__(self, replies=None, error=None):
        self.replies, self.error, self.calls = list(replies or []), error, 0

    def invoke(self, _messages):
        self.calls += 1
        if self.error:
            raise self.error
        return AIMessage(content=json.dumps({"sections": self.replies.pop(0)}))


@pytest.fixture
def owned(monkeypatch):
    monkeypatch.setattr(service, "get_simulation_status", lambda sim_id, user_id: DATA["simulation"])
    monkeypatch.setattr(service, "load_report_data", lambda simulation, user_id: DATA)


def test_report_has_the_fixed_sections_and_markdown(owned):
    report = service.generate_report("sim-1", "user-1", llm=FakeLLM([GOOD]))
    assert [s["key"] for s in report["sections"]] == ["setup", "performance", "key_decisions", "benchmark", "disclaimer"]
    assert all("facts" not in s for s in report["sections"])
    assert GOOD[1]["narrative"] in report["markdown"]
    assert report["markdown"].startswith("# Simulation report: SPY")


def test_ollama_down_returns_503(owned):
    llm = FakeLLM(error=ConnectionError("connection refused"))
    with pytest.raises(HTTPException) as exc:
        service.generate_report("sim-1", "user-1", llm=llm)
    assert exc.value.status_code == 503
    assert "Ollama" in exc.value.detail


def test_database_error_returns_503(monkeypatch):
    monkeypatch.setattr(service, "get_simulation_status", lambda sim_id, user_id: DATA["simulation"])

    def broken(simulation, user_id):
        raise RuntimeError("connection reset")

    monkeypatch.setattr(service, "load_report_data", broken)
    with pytest.raises(HTTPException) as exc:
        service.generate_report("sim-1", "user-1", llm=FakeLLM())
    assert exc.value.status_code == 503
    assert exc.value.detail == service.DATABASE_UNAVAILABLE


def test_running_simulation_returns_409(monkeypatch):
    monkeypatch.setattr(service, "get_simulation_status", lambda sim_id, user_id: {**DATA["simulation"], "status": "RUNNING"})
    llm = FakeLLM()
    with pytest.raises(HTTPException) as exc:
        service.generate_report("sim-1", "user-1", llm=llm)
    assert exc.value.status_code == 409
    assert llm.calls == 0


# --- endpoint ---

@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id="user-1")
    return TestClient(app)


def test_non_owner_gets_404_and_no_data_is_loaded(client, monkeypatch):
    def not_owned(sim_id, user_id):
        raise HTTPException(status_code=404, detail="Simulation not found")

    def must_not_load(simulation, user_id):
        raise AssertionError("data of a foreign simulation must not be loaded")

    monkeypatch.setattr(service, "get_simulation_status", not_owned)
    monkeypatch.setattr(service, "load_report_data", must_not_load)

    response = client.get("/simulations/foreign-sim/report")
    assert response.status_code == 404
    assert response.json()["detail"] == "Simulation not found"


def test_endpoint_returns_the_response_model(client, owned, monkeypatch):
    monkeypatch.setattr(routes, "generate_report", lambda sim_id, user_id: service.generate_report(sim_id, user_id, llm=FakeLLM([GOOD])))
    response = client.get("/simulations/sim-1/report")
    assert response.status_code == 200
    body = response.json()
    assert body["simulation_id"] == "sim-1"
    assert body["sections"][2]["table"]["columns"][0] == "Bought"
