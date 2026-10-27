"""US-31 end to end: the explain graph with a scripted model and an in-memory database."""
import pytest
from langchain_core.messages import AIMessage

from app.agents.explain import tools as explain_tools
from app.agents.explain.graph import build_agent_graph
from app.agents.explain.run import run_explanation
from app.agents.explain.tools import describe_breakdown, reference_text
from tests.fake_supabase import FakeSupabase

SIM, USER, DAY = "sim-1", "user-1", "2023-10-05"

BREAKDOWN = {
    "regime": "TRENDING", "threshold": 0.1, "blended_score": 0.412, "decision": "BUY",
    "components": [
        {"strategy": "SMA", "based_on": "SMA", "direction": "BUY", "score": 0.6, "weight": 0.7, "contribution": 0.42, "reasoning": "x"},
        {"strategy": "RSI", "based_on": "RSI", "direction": "HOLD", "score": -0.03, "weight": 0.3, "contribution": -0.009, "reasoning": "y"},
    ],
}


class ScriptedModel:
    """Stands in for the chat model: returns the scripted messages one by one."""

    def __init__(self, *messages):
        self.messages = list(messages)
        self.seen = []

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.seen.append(messages)
        return self.messages.pop(0)


def call(name, call_id, **args):
    return {"name": name, "args": args or {"date": DAY}, "id": call_id}


@pytest.fixture
def db(monkeypatch):
    fake = FakeSupabase(
        simulation_signals=[{"simulation_id": SIM, "date": DAY, "price": 4500.5, "sma_short": 4510.25,
                             "sma_long": 4488.9, "rsi": 28.41, "bollinger_lower": 4401.2,
                             "bollinger_upper": 4602.7, "momentum": 0.0523,
                             "regime": "TRENDING", "regime_model_version": "wf-regime-v1@2023-01-03"}],
        simulation_decisions=[{"simulation_id": SIM, "date": DAY, "action": "BUY", "executed": True,
                               "reason": "Combined score=0.412 crossed BUY threshold [RSI=28.41]",
                               "rejection_reason": None, "breakdown": BREAKDOWN}],
    )
    monkeypatch.setattr(explain_tools, "supabase", fake)
    return fake


def run(model, reference=""):
    graph = build_agent_graph(SIM, USER, llm=model, reference=lambda: reference)
    return run_explanation(graph, DAY, {"configurable": {"thread_id": "t"}})


def honest_model(final):
    return ScriptedModel(
        AIMessage(content="", tool_calls=[call("get_decision", "1"), call("get_indicators", "2"),
                                          call("get_market_regime", "3"), call("get_ensemble_breakdown", "4")]),
        AIMessage(content=final),
    )


def test_every_tool_call_and_the_value_it_returned_is_in_the_trace(db):
    result = run(honest_model("The strategy bought because the RSI was 28.41."))
    assert [t["tool"] for t in result["trace"]] == [
        "get_decision", "get_indicators", "get_market_regime", "get_ensemble_breakdown"]
    assert all(t["arguments"] == {"date": DAY} for t in result["trace"])
    by_tool = {t["tool"]: t["result"] for t in result["trace"]}
    assert "RSI: 28.41" in by_tool["get_indicators"]
    assert "Action: BUY" in by_tool["get_decision"]
    assert "trending" in by_tool["get_market_regime"]
    assert "blended score +0.412" in by_tool["get_ensemble_breakdown"] and "weight 0.70" in by_tool["get_ensemble_breakdown"]


def test_a_grounded_answer_is_shown_as_written(db):
    answer = "On 2023-10-05 the strategy bought. The RSI was 28.41 and the blended score 0.412."
    result = run(honest_model(answer))
    assert result["text"] == answer
    assert result["verification"] == {"verified": True, "tools_called": 4, "removed": []}


def test_a_fabricated_value_is_caught_and_removed_before_the_student_sees_it(db):
    result = run(honest_model("The strategy bought because the RSI was 28.41. The RSI was 71.9 a week earlier."))
    assert "71.9" not in result["text"]
    assert "28.41" in result["text"]
    assert result["verification"]["verified"] is False
    assert result["verification"]["removed"][0]["problems"] == ["71.9"]


def test_an_answer_with_no_tool_calls_cannot_state_numbers(db):
    model = ScriptedModel(AIMessage(content="The RSI was 28.41 and the price 4500.5."))
    result = run(model)
    assert result["trace"] == []
    assert result["verification"]["verified"] is False and result["verification"]["tools_called"] == 0
    assert "28.41" not in result["text"]


def test_the_agent_can_still_loop_through_several_tool_rounds(db):
    model = ScriptedModel(
        AIMessage(content="", tool_calls=[call("get_decision", "1")]),
        AIMessage(content="", tool_calls=[call("get_indicators", "2")]),
        AIMessage(content="The RSI was 28.41."),
    )
    result = run(model)
    assert [t["tool"] for t in result["trace"]] == ["get_decision", "get_indicators"]
    assert result["verification"]["verified"] is True


def test_the_strategy_settings_may_be_quoted(db):
    snapshot = {"name": "Patient RSI", "base_strategy": "RSI", "params": {"period": 21, "oversold": 25, "overbought": 75}}
    reference = reference_text(["CUSTOM:Patient RSI"], [snapshot], None)
    answer = "The RSI was 28.41, close to the oversold limit of 25."
    assert run(honest_model(answer), reference)["verification"]["verified"] is True
    assert run(honest_model(answer), "")["verification"]["verified"] is False  # without the definition, 25 is unbacked


def test_the_model_is_told_to_use_the_new_tools(db):
    model = honest_model("ok")
    run(model)
    system_prompt = model.seen[0][0].content
    assert "get_market_regime" in system_prompt and "get_ensemble_breakdown" in system_prompt


# ---- tools --------------------------------------------------------------------------------------------

def test_breakdown_text_names_each_strategy_with_score_and_weight():
    text = describe_breakdown(BREAKDOWN)
    assert "SMA: signal BUY, score +0.600, weight 0.70" in text
    assert "RSI: signal HOLD, score -0.030, weight 0.30" in text
    assert "market regime: trending" in text
    assert "single strategy" in describe_breakdown(None)


def test_reference_text_covers_defaults_and_custom_parameters():
    snapshot = {"name": "Patient RSI", "base_strategy": "RSI", "params": {"period": 21, "oversold": 25, "overbought": 75}}
    text = reference_text(["SMA", "CUSTOM:Patient RSI"], [snapshot], 0.15)
    assert "SMA (SMA) parameters: short_period 5, long_period 20" in text
    assert "Patient RSI (RSI) parameters: period 21, oversold 25, overbought 75" in text
    assert "BUY above 0.15, SELL below -0.15" in text
