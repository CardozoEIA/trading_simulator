import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from app.modules.chat import history, memory, service


class FakeGraph:
    """Stands in for the real LangGraph so no Ollama is needed."""

    def __init__(self, result=None, error=None, events=None, state_values=None):
        self.result = result
        self.error = error
        self.events = events or []
        self.state_values = state_values or {}
        self.last_input = None
        self.last_config = None

    def get_state(self, config):
        return SimpleNamespace(values=self.state_values)

    def invoke(self, state, config=None):
        self.last_input = state
        self.last_config = config
        if self.error:
            raise self.error
        return self.result

    def stream(self, state, config=None, stream_mode=None):
        self.last_input = state
        self.last_config = config
        if self.error:
            raise self.error
        yield from self.events


RESULT = {
    "messages": [AIMessage(content="It sold because of the stop-loss.")],
    "next_step": "explain_agent",
    "last_date_discussed": "2023-10-19",
    "proposed_change": None,
}


@pytest.fixture
def saved(monkeypatch):
    """Records what would be written to the history table."""
    turns = []
    monkeypatch.setattr(service, "_ensure_owner", lambda s, u: None)
    monkeypatch.setattr(history, "load_history", lambda *a, **k: [])
    monkeypatch.setattr(
        memory,
        "remember_turn",
        lambda user_id, simulation_id, question, payload: turns.append((question, payload)),
    )
    return turns


def use_graph(monkeypatch, graph):
    monkeypatch.setattr(service, "build_conversation_graph", lambda *a, **k: graph)


class FakeCheckpointer:
    def __init__(self):
        self.deleted = []

    def delete_thread(self, thread_id):
        self.deleted.append(thread_id)


# ---------- chat ----------

def test_chat_returns_reply_route_date_and_suggestions(monkeypatch, saved):
    graph = FakeGraph(result=RESULT)
    use_graph(monkeypatch, graph)

    result = service.chat("sim-1", "user-1", "Why did it sell on day 16?")

    assert result["reply"] == "It sold because of the stop-loss."
    assert result["route"] == "explain_agent"
    assert result["date"] == "2023-10-19"
    assert "And the next day?" in result["suggestions"]
    assert result["proposed_change"] is None
    assert graph.last_config["configurable"]["thread_id"] == "sim-1:user-1:chat"


def test_chat_saves_the_turn(monkeypatch, saved):
    use_graph(monkeypatch, FakeGraph(result=RESULT))

    service.chat("sim-1", "user-1", "Why did it sell on day 16?")

    assert len(saved) == 1
    assert saved[0][0] == "Why did it sell on day 16?"
    assert saved[0][1]["reply"] == "It sold because of the stop-loss."


def test_chat_rejects_simulation_of_another_user(monkeypatch):
    def deny(simulation_id, user_id):
        raise HTTPException(status_code=404, detail="Simulation not found")

    def must_not_be_called(*args, **kwargs):
        raise AssertionError("Graph must not be built for a foreign simulation")

    monkeypatch.setattr(service, "_ensure_owner", deny)
    monkeypatch.setattr(service, "build_conversation_graph", must_not_be_called)

    with pytest.raises(HTTPException) as error:
        service.chat("sim-1", "intruder", "Why did it sell?")

    assert error.value.status_code == 404


def test_chat_returns_503_when_the_model_is_down(monkeypatch, saved):
    use_graph(monkeypatch, FakeGraph(error=ConnectionError("Ollama is not running")))

    with pytest.raises(HTTPException) as error:
        service.chat("sim-1", "user-1", "Why did it sell?")

    assert error.value.status_code == 503
    assert saved == []


# ---------- US-25: memory across sessions ----------

def test_after_a_restart_the_thread_is_rebuilt_from_the_database(monkeypatch, saved):
    graph = FakeGraph(result=RESULT)  # empty in-memory state = server just restarted
    use_graph(monkeypatch, graph)
    monkeypatch.setattr(
        history,
        "load_history",
        lambda *a, **k: [
            {"role": "user", "content": "Why day 16?", "route": None, "date": None},
            {"role": "assistant", "content": "Because of the stop-loss.", "route": "explain_agent", "date": "2023-10-19"},
        ],
    )

    service.chat("sim-1", "user-1", "And the next day?")

    sent = graph.last_input

    assert sent["last_date_discussed"] == "2023-10-19"
    assert [type(m).__name__ for m in sent["messages"]] == ["HumanMessage", "AIMessage", "HumanMessage"]
    assert sent["messages"][-1].content == "And the next day?"


def test_a_live_thread_is_not_overwritten_by_the_database(monkeypatch, saved):
    graph = FakeGraph(result=RESULT, state_values={"messages": [HumanMessage(content="earlier")]})
    use_graph(monkeypatch, graph)

    def must_not_load(*args, **kwargs):
        raise AssertionError("History must not be loaded when the thread is alive")

    monkeypatch.setattr(history, "load_history", must_not_load)

    service.chat("sim-1", "user-1", "And the next day?")

    assert "last_date_discussed" not in graph.last_input
    assert len(graph.last_input["messages"]) == 1


def test_history_endpoint_returns_messages_and_suggestions(monkeypatch):
    monkeypatch.setattr(service, "_ensure_owner", lambda s, u: None)
    monkeypatch.setattr(
        history,
        "load_history",
        lambda *a, **k: [
            {"role": "user", "content": "q", "route": None, "date": None},
            {"role": "assistant", "content": "a", "route": "explain_agent", "date": "2023-10-19"},
        ],
    )

    result = service.get_history("sim-1", "user-1")

    assert len(result["messages"]) == 2
    assert "And the next day?" in result["suggestions"]


def test_history_of_a_foreign_simulation_is_a_404(monkeypatch):
    def deny(simulation_id, user_id):
        raise HTTPException(status_code=404, detail="Simulation not found")

    monkeypatch.setattr(service, "_ensure_owner", deny)

    with pytest.raises(HTTPException) as error:
        service.get_history("sim-1", "intruder")

    assert error.value.status_code == 404


def test_reset_clears_the_database_and_the_checkpointer(monkeypatch):
    calls = []
    checkpointer = FakeCheckpointer()
    monkeypatch.setattr(service, "_ensure_owner", lambda s, u: None)
    monkeypatch.setattr(service, "get_checkpointer", lambda: checkpointer)
    monkeypatch.setattr(history, "clear_history", lambda user_id, simulation_id: calls.append(("db", user_id, simulation_id)))

    service.reset_conversation("sim-1", "user-1")

    assert calls == [("db", "user-1", "sim-1")]
    assert checkpointer.deleted == ["sim-1:user-1:chat"]


# ---------- US-25: each student only reaches their own memory ----------

def test_two_students_never_share_a_conversation_thread(monkeypatch, saved):
    graph = FakeGraph(result=RESULT)
    use_graph(monkeypatch, graph)

    service.chat("sim-1", "alice", "Why did it sell on day 16?")
    alice_thread = graph.last_config["configurable"]["thread_id"]

    service.chat("sim-1", "bob", "Why did it sell on day 16?")
    bob_thread = graph.last_config["configurable"]["thread_id"]

    assert alice_thread == "sim-1:alice:chat"
    assert bob_thread == "sim-1:bob:chat"


def test_history_is_always_read_with_the_students_own_id(monkeypatch):
    asked = []
    monkeypatch.setattr(service, "_ensure_owner", lambda s, u: None)
    monkeypatch.setattr(history, "load_history", lambda user_id, simulation_id, **k: asked.append(user_id) or [])

    service.get_history("sim-1", "alice")
    service.get_history("sim-1", "bob")

    assert asked == ["alice", "bob"]


def test_reset_only_touches_the_students_own_thread(monkeypatch):
    checkpointer = FakeCheckpointer()
    cleared = []
    monkeypatch.setattr(service, "_ensure_owner", lambda s, u: None)
    monkeypatch.setattr(service, "get_checkpointer", lambda: checkpointer)
    monkeypatch.setattr(history, "clear_history", lambda user_id, simulation_id: cleared.append(user_id))

    service.reset_conversation("sim-1", "alice")

    assert cleared == ["alice"]
    assert checkpointer.deleted == ["sim-1:alice:chat"]


def test_saving_history_never_breaks_the_chat(monkeypatch):
    class Broken:
        def table(self, name):
            raise ConnectionError("database down")

    monkeypatch.setattr(history, "supabase", Broken())

    history.save_turn("user-1", "sim-1", "q", {"reply": "a"})  # must not raise

    assert history.load_history("user-1", "sim-1") == []


# ---------- streaming ----------

def parse_sse(chunks: list[str]) -> list[tuple[str, dict]]:
    events = []
    for raw in "".join(chunks).strip().split("\n\n"):
        lines = raw.split("\n")
        events.append((lines[0].removeprefix("event: "), json.loads(lines[1].removeprefix("data: "))))
    return events


def test_stream_sends_tokens_then_done(monkeypatch, saved):
    graph = FakeGraph(
        events=[
            ("values", {"messages": [HumanMessage(content="q")]}),
            ("messages", (AIMessageChunk(content="It sold "), {"langgraph_node": "agent"})),
            ("messages", (AIMessageChunk(content="because."), {"langgraph_node": "agent"})),
            ("values", RESULT),
        ]
    )
    use_graph(monkeypatch, graph)

    events = parse_sse(list(service.chat_stream("sim-1", "user-1", "Why?")))

    assert [name for name, _ in events] == ["token", "token", "done"]
    assert events[0][1]["text"] == "It sold "
    assert events[-1][1]["reply"] == "It sold because of the stop-loss."
    assert events[-1][1]["suggestions"]
    assert len(saved) == 1


def test_stream_hides_the_router_json_and_tool_calls(monkeypatch, saved):
    graph = FakeGraph(
        events=[
            ("messages", (AIMessageChunk(content='{"next_step": "answer"}'), {"langgraph_node": "supervisor"})),
            (
                "messages",
                (
                    AIMessageChunk(content="", tool_call_chunks=[{"name": "get_price", "args": "{}", "id": "1", "index": 0}]),
                    {"langgraph_node": "agent"},
                ),
            ),
            ("messages", (AIMessage(content="whole message, not a chunk"), {"langgraph_node": "agent"})),
            ("values", RESULT),
        ]
    )
    use_graph(monkeypatch, graph)

    events = parse_sse(list(service.chat_stream("sim-1", "user-1", "Why?")))

    assert [name for name, _ in events] == ["done"]


def test_stream_reports_a_model_failure_as_an_event(monkeypatch, saved):
    use_graph(monkeypatch, FakeGraph(error=ConnectionError("Ollama is not running")))

    events = parse_sse(list(service.chat_stream("sim-1", "user-1", "Why?")))

    assert [name for name, _ in events] == ["error"]
    assert "not available" in events[0][1]["detail"]
    assert saved == []


def test_stream_of_a_foreign_simulation_fails_before_streaming(monkeypatch):
    def deny(simulation_id, user_id):
        raise HTTPException(status_code=404, detail="Simulation not found")

    monkeypatch.setattr(service, "_ensure_owner", deny)

    with pytest.raises(HTTPException) as error:
        service.chat_stream("sim-1", "intruder", "Why?")

    assert error.value.status_code == 404