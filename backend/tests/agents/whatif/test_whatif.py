# tests/agents/whatif/test_whatif.py
import copy
import re
import time

import pytest
from fastapi import HTTPException

from app.agents.whatif import graph as whatif_graph
from app.agents.whatif.plan import SUPPORTED_PARAMETERS, expected_effect, plan_steps
from app.modules.whatif.service import run_what_if
from tests.agents.chat.test_conversation import ask, make_graph, offline, payload  # noqa: F401 (fixture)

ORIGINAL = {
    "id": "cfg-original", "user_id": "user-1", "asset": "SP500",
    "start_date": "2023-01-02", "end_date": "2023-06-30", "initial_capital": 10000.0,
    "strategies": ["SMA", "RSI"],
    "risk": {"configuration_id": "cfg-original", "stop_loss_percentage": 5.0,
             "max_position_size": 50.0, "max_drawdown": 20.0},
}
COMPARISON = {"winner": "b", "explanation": "verified text"}


class FakeBackend:
    """Stands in for the services the what-if writes through, and records every call."""

    def __init__(self, owner="user-1", status="FINISHED"):
        self.owner, self.status = owner, status
        self.original = copy.deepcopy(ORIGINAL)
        self.saved_configurations, self.saved_risks, self.runs, self.compares = [], [], [], []

    def install(self, monkeypatch):
        def status(simulation_id, user_id):
            if user_id != self.owner:
                raise HTTPException(status_code=404, detail="Simulation not found")
            return {"id": simulation_id, "configuration_id": "cfg-original", "status": self.status}

        def full_configuration(configuration_id, user_id):
            assert configuration_id == "cfg-original"
            return copy.deepcopy(self.original)  # callers get a copy, like a fresh database read

        def save_configuration(configuration, user_id, records):
            self.saved_configurations.append((configuration, user_id))
            return {"id": "cfg-new"}

        def save_risk(risk, user_id):
            self.saved_risks.append((risk, user_id))
            return {"id": "risk-new"}

        monkeypatch.setattr(whatif_graph, "get_simulation_status", status)
        monkeypatch.setattr(whatif_graph, "get_full_configuration", full_configuration)
        monkeypatch.setattr(whatif_graph, "validate_configuration", lambda configuration: 120)
        monkeypatch.setattr(whatif_graph, "save_configuration", save_configuration)
        monkeypatch.setattr(whatif_graph, "validate_risk_configuration", lambda risk, user_id: None)
        monkeypatch.setattr(whatif_graph, "save_risk_configuration", save_risk)
        monkeypatch.setattr(
            whatif_graph, "compare_simulations",
            lambda a, b, user_id, llm=None, config=None: self.compares.append((a, b, user_id)) or COMPARISON,
        )
        monkeypatch.setattr(
            whatif_graph, "compare_without_explanation",
            lambda a, b, user_id: {**COMPARISON, "explanation": None},
        )
        return self

    def runner(self, configuration_id, user_id):
        self.runs.append((configuration_id, user_id))
        return {"id": "sim-new", "configuration_id": configuration_id, "status": "FINISHED"}


@pytest.fixture
def backend(monkeypatch):
    return FakeBackend().install(monkeypatch)


def what_if(backend, user_id="user-1", parameter="stop_loss_percentage", value=3, **options):
    options.setdefault("runner", backend.runner)
    return run_what_if("sim-original", user_id, parameter, value, **options)


# --- plan and fallback text ---

def test_plan_lists_the_ordered_steps():
    proposal = {"label": "stop-loss", "suggested": 3.0}
    assert plan_steps(proposal) == [
        "Read the current configuration of this simulation",
        "Run a copy with the stop-loss at 3% (this simulation is not changed)",
        "Compare both runs",
    ]


@pytest.mark.parametrize("parameter", SUPPORTED_PARAMETERS)
@pytest.mark.parametrize("current, suggested", [(5.0, 3.0), (5.0, 8.0), (None, 3.0)])
def test_fallback_explanation_has_no_numbers_and_is_labelled(parameter, current, suggested):
    text = expected_effect(parameter, current, suggested)
    assert not re.search(r"\d", text)
    assert text.startswith("This is a general explanation of the expected effect, not a simulation result.")


# --- human in the loop ---

def test_chat_only_proposes_and_never_runs_the_what_if(backend):
    graph = make_graph({"stop-loss": payload("propose_change", parameter="stop_loss_percentage", value=3)})
    result = ask(graph, "What if the stop-loss were 3%?")
    assert result["proposed_change"]["plan"][1].startswith("Run a copy with the stop-loss at 3%")
    assert backend.saved_configurations == backend.saved_risks == backend.runs == []


# --- the confirmed run ---

def test_what_if_copies_the_configuration_runs_it_and_compares(backend):
    result = what_if(backend)

    assert result["status"] == "COMPLETED"
    assert (result["original_id"], result["what_if_id"]) == ("sim-original", "sim-new")
    assert result["change"]["current"] == 5.0 and result["change"]["suggested"] == 3.0
    assert result["comparison"] == COMPARISON
    assert backend.compares == [("sim-original", "sim-new", "user-1")]

    (configuration, owner), = backend.saved_configurations
    assert owner == "user-1"
    assert (configuration.asset, str(configuration.start_date), str(configuration.end_date)) == (
        "SP500", "2023-01-02", "2023-06-30")
    assert configuration.initial_capital == 10000.0
    assert [s.value for s in configuration.strategies] == ["SMA", "RSI"]

    (risk, _), = backend.saved_risks
    assert risk.configuration_id == "cfg-new"   # the copy, never the original configuration
    assert (risk.stop_loss_percentage, risk.max_position_size, risk.max_drawdown) == (3.0, 50.0, 20.0)


def test_new_simulation_runs_on_the_new_configuration(backend):
    what_if(backend)
    assert backend.runs == [("cfg-new", "user-1")]


def test_original_configuration_is_unchanged(backend):
    what_if(backend, parameter="max_drawdown", value=10)
    assert backend.original == ORIGINAL


def test_comparison_without_the_agent_when_it_is_unavailable(backend, monkeypatch):
    def agent_down(*args, **kwargs):
        raise HTTPException(status_code=503, detail="Ollama down")

    monkeypatch.setattr(whatif_graph, "compare_simulations", agent_down)
    result = what_if(backend)
    assert result["status"] == "COMPLETED"
    assert result["comparison"]["explanation"] is None
    assert "could not explain" in result["message"]


# --- graceful degradation ---

def test_slow_rerun_falls_back_to_a_qualitative_explanation(backend):
    def slow(configuration_id, user_id):
        time.sleep(0.5)
        return {"id": "sim-late"}

    result = what_if(backend, runner=slow, timeout=0.05)
    assert result["status"] == "FALLBACK"
    assert result["what_if_id"] is None and result["comparison"] is None
    assert not re.search(r"\d", result["fallback"])
    assert "taking too long" in result["message"]


def test_failed_rerun_falls_back_to_a_qualitative_explanation(backend):
    def broken(configuration_id, user_id):
        raise RuntimeError("engine crashed")

    result = what_if(backend, runner=broken)
    assert result["status"] == "FALLBACK"
    assert "tighter stop-loss" in result["fallback"]
    assert backend.compares == []


# --- access and validation ---

def test_non_owner_gets_404_and_nothing_is_written(backend):
    with pytest.raises(HTTPException) as exc:
        what_if(backend, user_id="someone-else")
    assert exc.value.status_code == 404
    assert backend.saved_configurations == backend.saved_risks == backend.runs == []


@pytest.mark.parametrize("value", [0, 150, 5])  # out of range, and the same as the current stop-loss
def test_invalid_change_is_400_and_nothing_is_written(backend, value):
    with pytest.raises(HTTPException) as exc:
        what_if(backend, value=value)
    assert exc.value.status_code == 400
    assert backend.saved_configurations == backend.runs == []


def test_running_simulation_is_409(monkeypatch):
    backend = FakeBackend(status="RUNNING").install(monkeypatch)
    with pytest.raises(HTTPException) as exc:
        what_if(backend)
    assert exc.value.status_code == 409
