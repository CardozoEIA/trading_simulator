# tests/agents/chat/test_compare_route.py
import json
from types import SimpleNamespace

import pytest

from app.agents.chat import graph as graph_module
from app.agents.chat.routing.router import classify_question
from app.agents.chat.support.comparisons import NO_OTHER, resolve_comparison
from app.agents.chat.support.followups import suggest_followups
from tests.agents.chat.test_conversation import ask, make_graph, offline, payload  # noqa: F401 (fixture)

# newest first, as returned by list_my_simulations; "sim-1" is the simulation open in the chat
HISTORY = [
    {"id": "sim-3", "status": "RUNNING", "asset": "SPY", "strategies": ["RSI"],
     "start_date": "2024-01-01", "end_date": "2024-06-30", "total_return_pct": None},
    {"id": "sim-1", "status": "FINISHED", "asset": "SPY", "strategies": ["SMA"],
     "start_date": "2023-01-02", "end_date": "2023-06-30", "total_return_pct": 8.0},
    {"id": "sim-0", "status": "STOPPED_BY_RISK", "asset": "SPY", "strategies": ["SMA", "RSI"],
     "start_date": "2022-01-03", "end_date": "2022-12-30", "total_return_pct": -2.5},
    {"id": "sim-9", "status": "FINISHED", "asset": "SPY", "strategies": ["MOMENTUM"],
     "start_date": "2021-01-04", "end_date": "2021-12-31", "total_return_pct": 12.0},
]


# ---------- resolving the other simulation ----------

def test_previous_means_the_run_before_this_one():
    assert resolve_comparison(HISTORY, "sim-1", "previous", None) == ("sim-0", None)


def test_number_picks_from_the_listed_menu():
    # the menu skips this simulation and running ones: 1 = sim-0, 2 = sim-9
    assert resolve_comparison(HISTORY, "sim-1", None, 2) == ("sim-9", None)
    other, message = resolve_comparison(HISTORY, "sim-1", None, 7)
    assert other is None and "no simulation number 7" in message


def test_ambiguous_request_lists_the_recent_simulations():
    other, message = resolve_comparison(HISTORY, "sim-1", None, None)
    assert other is None
    assert "1. SPY · SMA, RSI · 2022-01-03 to 2022-12-30 (return -2.50%)" in message
    assert "2. SPY · MOMENTUM · 2021-01-04 to 2021-12-31 (return +12.00%)" in message
    assert "sim-3" not in message and "RSI · 2024-01-01" not in message  # running runs are not offered


def test_oldest_simulation_has_no_previous_one():
    other, message = resolve_comparison(HISTORY, "sim-9", "previous", None)
    assert other is None and "no previous one" in message


def test_nothing_to_compare_with():
    assert resolve_comparison(HISTORY[1:2], "sim-1", "previous", None) == (None, NO_OTHER)


# ---------- router and conversation graph ----------

def test_router_accepts_the_compare_route_and_its_fields():
    reply = json.dumps(payload("compare", compare_with="previous", simulation_number="2"))
    llm = SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=reply))
    decision = classify_question(llm, "Compare this run with my previous one", None)
    assert (decision["next_step"], decision["compare_with"], decision["simulation_number"]) == ("compare", "previous", 2)


def test_router_ignores_unknown_compare_references():
    reply = json.dumps(payload("compare", compare_with="the green one"))
    llm = SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=reply))
    assert classify_question(llm, "compare", None)["compare_with"] is None


@pytest.fixture
def compare_backend(monkeypatch):
    calls = []
    monkeypatch.setattr(graph_module, "list_my_simulations", lambda user_id: HISTORY)
    monkeypatch.setattr(
        graph_module, "compare_simulations_text",
        lambda simulation_id, other_id, user_id, config=None: calls.append((simulation_id, other_id, user_id)) or "COMPARISON",
    )
    return calls


def test_comparison_question_is_routed_to_compare(compare_backend):
    graph = make_graph({"previous one": payload("compare", compare_with="previous")})
    result = ask(graph, "Compare this run with my previous one")
    assert result["next_step"] == "compare"
    assert result["messages"][-1].content == "COMPARISON"
    assert compare_backend == [("sim-1", "sim-0", "user-1")]


def test_ambiguous_comparison_asks_back_with_the_list(compare_backend):
    graph = make_graph({"another": payload("compare")})
    result = ask(graph, "Compare it with another simulation")
    assert result["next_step"] == "clarify"
    assert "Which simulation should I compare this one with?" in result["messages"][-1].content
    assert compare_backend == []


def test_failed_comparison_degrades_to_a_message(monkeypatch):
    monkeypatch.setattr(graph_module, "list_my_simulations", lambda user_id: HISTORY)

    def down(*args):
        raise ConnectionError("ollama down")

    monkeypatch.setattr(graph_module, "compare_simulations_text", down)
    graph = make_graph({"previous": payload("compare", compare_with="previous")})
    assert "unavailable" in ask(graph, "Compare with my previous one")["messages"][-1].content


def test_compare_route_has_followups():
    assert len(suggest_followups("compare")) == 3
