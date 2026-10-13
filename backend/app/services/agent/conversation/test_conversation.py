import json
from types import SimpleNamespace

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph

from app.services.agent.conversation import graph as graph_module
from app.services.agent.conversation import tools as tools_module
from app.services.agent.conversation.followups import suggest_followups
from app.services.agent.conversation.graph import build_conversation_graph
from app.services.agent.conversation.proposals import build_proposal
from app.services.agent.conversation.prompts import build_conceptual_prompt
from app.services.agent.conversation.router import (
    classify_question,
    parse_int,
    parse_number,
)

DATES = [f"2023-10-{day:02d}" for day in range(1, 31)]


class ScriptedRouter:
    """Stands in for the router model: returns the JSON scripted for the question."""

    def __init__(self, script: dict[str, dict]):
        self.script = script

    def invoke(self, messages):
        text = messages[-1].content
        for fragment, payload in self.script.items():
            if fragment in text:
                return SimpleNamespace(content=json.dumps(payload))
        return SimpleNamespace(content=json.dumps({"next_step": "clarify", "message": "?"}))


def payload(next_step, **fields):
    base = {
        "next_step": next_step,
        "day_number": None,
        "offset": None,
        "date": None,
        "parameter": None,
        "value": None,
        "message": None,
    }
    return {**base, **fields}


class FakeAgentGraph:
    def invoke(self, state, config=None):
        text = state["messages"][-1].content
        return {"messages": [AIMessage(content=f"Explained: {text}")]}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(graph_module, "load_decision_dates", lambda simulation_id: DATES)
    monkeypatch.setattr(graph_module, "build_agent_graph", lambda *a, **k: FakeAgentGraph())
    monkeypatch.setattr(
        graph_module,
        "current_risk_values",
        lambda simulation_id: {
            "stop_loss_percentage": 2,
            "max_position_size": 50,
            "max_drawdown": 20,
        },
    )
    monkeypatch.setattr(graph_module, "summarize_simulation", lambda simulation_id: "OVERVIEW TEXT")
    monkeypatch.setattr(graph_module, "buy_and_hold_comparison", lambda simulation_id: "BENCHMARK TEXT")


def make_graph(script, chat_llm=None, memory_lookup=None):
    return build_conversation_graph(
        "sim-1",
        "user-1",
        llm=ScriptedRouter(script),
        chat_llm=chat_llm or GenericFakeChatModel(messages=iter([AIMessage(content="unused")])),
        checkpointer=MemorySaver(),
        memory_lookup=memory_lookup,
    )


def ask(graph, question, thread="t1"):
    return graph.invoke(
        {"messages": [HumanMessage(content=question)], "simulation_id": "sim-1"},
        config={"configurable": {"thread_id": thread}},
    )


# ---------- router ----------

def test_classify_returns_clarify_on_invalid_json():
    llm = SimpleNamespace(invoke=lambda messages: SimpleNamespace(content="not json"))
    assert classify_question(llm, "hi", None)["next_step"] == "clarify"


def test_classify_returns_clarify_on_unknown_route():
    llm = SimpleNamespace(invoke=lambda m: SimpleNamespace(content=json.dumps({"next_step": "hack"})))
    assert classify_question(llm, "hi", None)["next_step"] == "clarify"


def test_classify_returns_clarify_when_json_is_not_an_object():
    llm = SimpleNamespace(invoke=lambda m: SimpleNamespace(content="[1, 2]"))
    assert classify_question(llm, "hi", None)["next_step"] == "clarify"


def test_parsers():
    assert parse_int("12") == 12
    assert parse_int(True) is None
    assert parse_number("3%") == 3.0
    assert parse_number("abc") is None
    assert parse_number(float("nan")) is None
    assert parse_number(True) is None


# ---------- routing and multi-turn memory ----------

def test_multi_turn_keeps_the_last_discussed_day():
    graph = make_graph(
        {
            "day 16": payload("explain_agent", day_number=16),
            "next day": payload("explain_agent", offset=1),
            "do that": payload("explain_agent", offset=0),
        }
    )

    first = ask(graph, "Why did it sell on day 16?")
    assert first["last_date_discussed"] == "2023-10-16"
    assert "2023-10-16" in first["messages"][-1].content

    second = ask(graph, "And the next day?")
    assert second["last_date_discussed"] == "2023-10-17"

    third = ask(graph, "Why did it do that?")
    assert third["last_date_discussed"] == "2023-10-17"


def test_relative_question_without_context_asks_for_a_day():
    graph = make_graph({"next day": payload("explain_agent", offset=1)})

    result = ask(graph, "And the next day?")

    assert result["next_step"] == "clarify"
    assert "specify a day" in result["messages"][-1].content


def test_day_out_of_range_is_rejected_in_code():
    graph = make_graph({"day 9999": payload("explain_agent", day_number=9999)})

    result = ask(graph, "Why did it sell on day 9999?")

    assert result["next_step"] == "clarify"
    assert "out of range" in result["messages"][-1].content


def test_date_without_year_in_question_asks_for_the_year():
    graph = make_graph({"March 15": payload("explain_agent", date="2023-03-15")})

    result = ask(graph, "Why did it sell on March 15?")

    assert result["messages"][-1].content == "Which year do you mean?"


def test_insights_and_benchmark_routes():
    graph = make_graph(
        {
            "overview": payload("insights_agent"),
            "buy & hold": payload("answer"),
        }
    )

    assert ask(graph, "Give me an overview")["messages"][-1].content == "OVERVIEW TEXT"
    assert ask(graph, "Did it beat buy & hold?")["messages"][-1].content == "BENCHMARK TEXT"


def test_conceptual_route_uses_the_chat_model():
    chat_llm = GenericFakeChatModel(messages=iter([AIMessage(content="RSI measures momentum.")]))
    graph = make_graph({"RSI": payload("conceptual")}, chat_llm=chat_llm)

    result = ask(graph, "What is the RSI?")

    assert result["next_step"] == "conceptual"
    assert result["messages"][-1].content == "RSI measures momentum."


def test_conceptual_prompt_is_grounded_in_the_glossary():
    prompt = build_conceptual_prompt()

    assert "Sharpe ratio" in prompt
    assert "Only" in prompt or "ONLY" in prompt


class RecordingChat:
    """Keeps the prompts the answer model receives."""

    def __init__(self):
        self.calls = []

    def invoke(self, messages):
        self.calls.append(messages)
        return AIMessage(content="ok")


def test_conceptual_answers_use_the_retrieved_memory():
    chat = RecordingChat()
    graph = make_graph(
        {"RSI": payload("conceptual")},
        chat_llm=chat,
        memory_lookup=lambda question: "Earlier in this conversation (the most relevant turns):\nStudent: What is a stop-loss?",
    )

    ask(graph, "What is the RSI?")

    assert "Student: What is a stop-loss?" in chat.calls[0][0].content


def test_conceptual_answers_work_when_there_is_no_memory_to_add():
    chat = RecordingChat()
    graph = make_graph({"RSI": payload("conceptual")}, chat_llm=chat, memory_lookup=lambda question: None)

    result = ask(graph, "What is the RSI?")

    assert result["messages"][-1].content == "ok"
    assert "Earlier in this conversation" not in chat.calls[0][0].content


def test_a_failing_memory_lookup_does_not_break_the_answer():
    def broken(question):
        raise RuntimeError("embedding service down")

    graph = make_graph({"RSI": payload("conceptual")}, chat_llm=RecordingChat(), memory_lookup=broken)

    assert ask(graph, "What is the RSI?")["messages"][-1].content == "ok"


def test_conceptual_route_survives_a_model_failure():
    class Broken:
        def invoke(self, messages):
            raise ConnectionError("Ollama is down")

    graph = make_graph({"RSI": payload("conceptual")}, chat_llm=Broken())

    result = ask(graph, "What is the RSI?")

    assert "Ollama" in result["messages"][-1].content


# ---------- human in the loop ----------

def test_proposal_is_returned_but_not_applied():
    graph = make_graph(
        {"stop-loss": payload("propose_change", parameter="stop_loss_percentage", value=3)}
    )

    result = ask(graph, "Try a 3% stop-loss")

    assert result["next_step"] == "propose_change"
    assert result["proposed_change"] == {
        "parameter": "stop_loss_percentage",
        "label": "stop-loss",
        "current": 2.0,
        "suggested": 3.0,
    }
    assert "will not change" in result["messages"][-1].content


def test_proposal_does_not_leak_into_the_next_turn():
    graph = make_graph(
        {
            "stop-loss": payload("propose_change", parameter="stop_loss_percentage", value=3),
            "overview": payload("insights_agent"),
        }
    )

    ask(graph, "Try a 3% stop-loss")
    result = ask(graph, "Give me an overview")

    assert result["proposed_change"] is None


def test_the_conversation_never_writes_to_the_database(monkeypatch):
    """Human-in-the-loop: the agent has no write path at all."""

    class ReadOnlyTable:
        def select(self, *a, **k):
            return self

        def eq(self, *a, **k):
            return self

        def limit(self, *a, **k):
            return self

        def order(self, *a, **k):
            return self

        def execute(self):
            return SimpleNamespace(data=[])

        def insert(self, *a, **k):
            raise AssertionError("write attempted")

        update = delete = upsert = insert

    fake = SimpleNamespace(table=lambda name: ReadOnlyTable())
    monkeypatch.setattr(tools_module, "supabase", fake)
    monkeypatch.setattr(graph_module, "current_risk_values", tools_module.current_risk_values)

    graph = make_graph(
        {"stop-loss": payload("propose_change", parameter="stop_loss_percentage", value=3)}
    )

    result = ask(graph, "Try a 3% stop-loss")

    # No risk limits found -> still only a proposal, still no write.
    assert result["proposed_change"]["suggested"] == 3.0


@pytest.mark.parametrize(
    "parameter, value, expected_fragment",
    [
        ("stop_loss_percentage", 0, "greater than 0"),
        ("stop_loss_percentage", 150, "greater than 0"),
        ("stop_loss_percentage", 2, "already"),
        ("account_balance", 3, "Which risk limit"),
        ("stop_loss_percentage", None, "Which risk limit"),
    ],
)
def test_invalid_proposals_are_rejected(parameter, value, expected_fragment):
    proposal, error = build_proposal(parameter, value, {"stop_loss_percentage": 2})

    assert proposal is None
    assert expected_fragment in error


# ---------- follow-up suggestions ----------

@pytest.mark.parametrize(
    "route, date",
    [
        ("explain_agent", "2023-10-16"),
        ("insights_agent", None),
        ("answer", None),
        ("conceptual", None),
        ("propose_change", None),
        ("clarify", None),
        (None, None),
    ],
)
def test_every_route_offers_three_distinct_suggestions(route, date):
    suggestions = suggest_followups(route, date)

    assert len(suggestions) == 3
    assert len(set(suggestions)) == 3


def test_day_suggestions_only_appear_after_an_explanation():
    assert "And the next day?" in suggest_followups("explain_agent", "2023-10-16")
    assert "And the next day?" not in suggest_followups("clarify", "2023-10-16")


# ---------- streaming through the nested explain agent ----------

def test_tokens_of_the_nested_agent_reach_the_stream(monkeypatch):
    """The explain agent runs a graph inside a node. Its tokens must still stream out."""

    def build_fake_agent(*args, **kwargs):
        model = GenericFakeChatModel(messages=iter([AIMessage(content="It sold because the stop-loss triggered.")]))

        def call_model(state: MessagesState):
            return {"messages": [model.invoke(state["messages"])]}

        inner = StateGraph(MessagesState)
        inner.add_node("agent", call_model)
        inner.add_edge(START, "agent")
        inner.add_edge("agent", END)
        return inner.compile(checkpointer=MemorySaver())

    monkeypatch.setattr(graph_module, "build_agent_graph", build_fake_agent)

    graph = make_graph({"day 16": payload("explain_agent", day_number=16)})

    tokens = []
    final = None

    for mode, data in graph.stream(
        {"messages": [HumanMessage(content="Why day 16?")], "simulation_id": "sim-1"},
        config={"configurable": {"thread_id": "stream-1"}},
        stream_mode=["messages", "values"],
    ):
        if mode == "messages":
            chunk, metadata = data
            tokens.append((chunk, metadata))
        elif mode == "values":
            final = data

    streamed = [
        chunk.content
        for chunk, metadata in tokens
        if type(chunk).__name__ == "AIMessageChunk" and chunk.content
    ]

    assert len(streamed) > 1
    assert "".join(streamed) == "It sold because the stop-loss triggered."
    assert final["messages"][-1].content == "It sold because the stop-loss triggered."