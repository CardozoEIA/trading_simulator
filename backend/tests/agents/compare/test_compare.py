# tests/agents/compare/test_compare.py
import json

import pytest
from fastapi import HTTPException
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from app.agents.compare import graph as compare_graph
from app.agents.compare import tools as compare_tools
from app.agents.compare.diff import configuration_diff, diff_facts, metrics_diff, winner
from app.agents.compare.verify import wrong_directions
from app.agents.insights.verify import unverified_values

SLICE_A = {
    "id": "sim-a", "status": "FINISHED", "stop_reason": None, "started_at": "2026-10-01T10:00:00",
    "configuration": {
        "asset": "SPY", "start_date": "2023-01-02", "end_date": "2023-06-30", "strategies": ["SMA"],
        "initial_capital": 1000.0, "stop_loss_percentage": 5.0, "max_position_size": 50.0, "max_drawdown": 20.0,
    },
    "metrics": {
        "total_return_pct": 8.0, "sharpe_ratio": 1.2, "max_drawdown_pct": 10.0, "win_rate": 50.0,
        "profit_factor": 1.5, "total_trades": 4, "winning_trades": 2, "final_value": 1080.0,
    },
    "benchmark": {"total_return_pct": 4.0, "final_capital": 1040.0},
    "highlights": [{"kind": "WORST_TRADE", "label": "Worst trade -$120.00",
                    "facts": "Bought on 2023-03-01 at $125.00 and sold on 2023-03-20 at $110.00: result -$120.00 (-12.00%)."}],
}
SLICE_B = {
    "id": "sim-b", "status": "STOPPED_BY_RISK", "stop_reason": "Max drawdown of 10% reached",
    "started_at": "2026-10-05T10:00:00",
    "configuration": {**SLICE_A["configuration"], "strategies": ["SMA", "RSI"], "stop_loss_percentage": 3.0},
    "metrics": {
        "total_return_pct": 3.5, "sharpe_ratio": 0.6, "max_drawdown_pct": 6.0, "win_rate": 75.0,
        "profit_factor": None, "total_trades": 4, "winning_trades": 4, "final_value": 1035.0,
    },
    "benchmark": {"total_return_pct": 4.0, "final_capital": 1040.0},
    "highlights": [],
}


def by_metric(rows):
    return {r["metric"]: r for r in rows}


# --- pure diff ---

def test_configuration_diff_marks_only_what_changed():
    rows = {r["field"]: r for r in configuration_diff(SLICE_A["configuration"], SLICE_B["configuration"])}
    assert {f for f, r in rows.items() if r["changed"]} == {"strategies", "stop_loss_percentage"}
    assert (rows["stop_loss_percentage"]["a"], rows["stop_loss_percentage"]["b"]) == ("5.00%", "3.00%")
    assert rows["strategies"]["b"] == "SMA, RSI"


def test_strategy_order_does_not_count_as_a_change():
    reordered = {**SLICE_B["configuration"], "strategies": ["RSI", "SMA"]}
    rows = {r["field"]: r for r in configuration_diff(SLICE_B["configuration"], reordered)}
    assert rows["strategies"]["changed"] is False


def test_metrics_diff_values_deltas_and_better_side():
    m = by_metric(metrics_diff(SLICE_A, SLICE_B))
    assert m["total_return_pct"]["delta"] == pytest.approx(-4.5)
    assert m["total_return_pct"]["delta_display"] == "-4.50 pts"
    assert m["total_return_pct"]["better"] == "a"
    assert m["max_drawdown_pct"]["better"] == "b"           # lower drawdown is better
    assert m["win_rate"]["better"] == "b"
    assert m["total_trades"]["better"] is None              # more trades is neither better nor worse
    assert m["final_value"]["delta_display"] == "-$45.00"
    # B had no losing trades: its profit factor is the best possible, shown as text, never as a number
    assert m["profit_factor"]["b"] is None and m["profit_factor"]["b_display"] == "No losing trades"
    assert m["profit_factor"]["better"] == "b"
    assert m["excess_return_pct"]["a_display"] == "+4.00 pts"
    assert m["excess_return_pct"]["b_display"] == "-0.50 pts"


def test_winner_is_the_higher_total_return_or_a_tie():
    assert winner(metrics_diff(SLICE_A, SLICE_B)) == "a"
    assert winner(metrics_diff(SLICE_B, SLICE_A)) == "b"
    assert winner(metrics_diff(SLICE_A, SLICE_A)) == "tie"


def test_win_rate_does_not_apply_without_completed_trades():
    no_trades = {**SLICE_B, "metrics": {**SLICE_B["metrics"], "total_trades": 0, "winning_trades": 0, "win_rate": 0.0}}
    m = by_metric(metrics_diff(SLICE_A, no_trades))
    assert m["win_rate"]["b_display"] == "n/a" and m["win_rate"]["better"] is None


def test_facts_state_differences_and_direction_explicitly():
    configuration = configuration_diff(SLICE_A["configuration"], SLICE_B["configuration"])
    metrics = metrics_diff(SLICE_A, SLICE_B)
    facts = diff_facts(SLICE_A, SLICE_B, configuration, metrics, winner(metrics))
    assert "Stop-loss: A 5.00%, B 3.00%." in facts
    assert "Max drawdown: A 10.00%, B 6.00% (difference B minus A: -4.00 pts); B had the smaller max drawdown (better)." in facts
    assert "By total return, simulation A performed better." in facts
    assert "Worst trade -$120.00" in facts


# --- tools: ownership on every call ---

def test_slice_of_a_foreign_simulation_is_404_and_loads_nothing(monkeypatch):
    def not_owned(simulation_id, user_id):
        raise HTTPException(status_code=404, detail="Simulation not found")

    def must_not_load(*args, **kwargs):
        raise AssertionError("data of a foreign simulation must not be loaded")

    monkeypatch.setattr(compare_tools, "get_simulation_status", not_owned)
    monkeypatch.setattr(compare_tools, "build_configuration_summary", must_not_load)
    monkeypatch.setattr(compare_tools, "load_simulation_data", must_not_load)

    _, simulation_slice = compare_tools.build_compare_tools("user-1")
    with pytest.raises(HTTPException) as exc:
        simulation_slice.invoke({"simulation_id": "foreign"})
    assert exc.value.status_code == 404


def test_slice_of_a_running_simulation_is_409(monkeypatch):
    monkeypatch.setattr(compare_tools, "get_simulation_status",
                        lambda sim_id, user_id: {"id": sim_id, "status": "RUNNING", "configuration_id": "c"})
    with pytest.raises(HTTPException) as exc:
        compare_tools.get_simulation_slice("sim-a", "user-1")
    assert exc.value.status_code == 409


def test_tools_are_bound_to_the_student(monkeypatch):
    seen = []
    monkeypatch.setattr(compare_tools, "get_simulation_history", lambda user_id: seen.append(user_id) or [])
    list_simulations, _ = compare_tools.build_compare_tools("user-1")
    assert json.loads(list_simulations.invoke({})) == []
    assert seen == ["user-1"]


# --- graph with fake tools and a scripted model ---

class ScriptedLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def invoke(self, _messages):
        self.calls += 1
        return AIMessage(content=json.dumps({"explanation": self.replies.pop(0)}))


@pytest.fixture
def fake_tools(monkeypatch):
    slices = {"sim-a": SLICE_A, "sim-b": SLICE_B}
    requested = []

    def build(user_id):
        @tool
        def list_simulations() -> str:
            """Fake list."""
            return "[]"

        @tool
        def simulation_slice(simulation_id: str) -> str:
            """Fake slice."""
            requested.append((user_id, simulation_id))
            return json.dumps(slices[simulation_id])

        return [list_simulations, simulation_slice]

    monkeypatch.setattr(compare_graph, "build_compare_tools", build)
    return requested


def run_graph(replies):
    llm = ScriptedLLM(replies)
    result = compare_graph.build_compare_graph(llm=llm).invoke(
        {"user_id": "user-1", "simulation_a": "sim-a", "simulation_b": "sim-b"}
    )
    return result, llm


GOOD = ("Simulation A performed better, with a total return of 8.00% against 3.50%. B likely gave up gains "
        "because its tighter stop-loss of 3.00% closed trades early, although its max drawdown was smaller at 6.00%.")


def test_graph_fetches_both_slices_for_the_student_and_explains(fake_tools):
    result, llm = run_graph([GOOD])
    assert sorted(fake_tools) == [("user-1", "sim-a"), ("user-1", "sim-b")]
    assert result["winner"] == "a"
    assert result["explanation"] == GOOD
    assert unverified_values(result["explanation"], result["facts"]) == []
    assert llm.calls == 1


def test_invented_value_is_retried_then_removed(fake_tools):
    invented = "A won because it returned 12.75% more than B."
    result, llm = run_graph([invented, GOOD])
    assert llm.calls == 2 and result["explanation"] == GOOD

    result, llm = run_graph([invented, invented])
    assert llm.calls == compare_graph.MAX_ATTEMPTS
    assert result["explanation"] is None
    assert result["metrics_diff"]  # the computed comparison is still returned


def test_comparison_the_wrong_way_round_is_detected():
    metrics = metrics_diff(SLICE_A, SLICE_B)  # drawdown: A 10.00%, B 6.00%
    assert wrong_directions("B had a larger drawdown than A.", metrics) == ["B had a larger drawdown"]
    assert wrong_directions("The larger drawdown in Simulation B hurt it.", metrics) == ["larger drawdown in Simulation B"]
    assert wrong_directions("A's higher Sharpe ratio and the smaller drawdown of B.", metrics) == []
    assert wrong_directions("Simulation A had a slightly lower total return.", metrics) == [
        "Simulation A had a slightly lower total return"]


def test_wrong_direction_is_retried(fake_tools):
    wrong = "Simulation A performed better with 8.00%, but B had a larger drawdown of 6.00%."
    result, llm = run_graph([wrong, GOOD])
    assert llm.calls == 2 and result["explanation"] == GOOD


def test_promises_are_rejected(fake_tools):
    promise = "A is guaranteed to keep returning 8.00%."
    result, llm = run_graph([promise, GOOD])
    assert llm.calls == 2 and result["explanation"] == GOOD
