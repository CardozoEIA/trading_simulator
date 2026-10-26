# tests/agents/common/test_tracing.py
import sys
from typing import TypedDict
from uuid import uuid4

import pytest
from langchain_core.callbacks import BaseCallbackHandler, CallbackManager
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph

from app.agents.chat import graph as chat_graph
from app.agents.common import tracing
from tests.agents.chat.test_conversation import ScriptedRouter, offline, payload  # noqa: F401 (fixture)


class FakeLangfuseHandler(BaseCallbackHandler):
    """Stands in for langfuse's CallbackHandler and records the runs it would trace."""

    def __init__(self):
        self.runs = {}

    def on_chain_start(self, serialized, inputs, *, run_id, parent_run_id=None, **kwargs):
        self.runs[run_id] = (kwargs.get("name"), parent_run_id)

    def ancestors(self, name):
        run_id = next(r for r, (n, _) in self.runs.items() if n == name)
        chain = []
        while (parent := self.runs[run_id][1]) is not None:
            chain.append(self.runs[parent][0])
            run_id = parent
        return chain


FakeLangfuseHandler.__module__ = "langfuse.langchain.fake"  # how child_config recognises tracing handlers


class StreamHandler(BaseCallbackHandler):
    """Like the handler LangGraph uses to stream tokens to the chat."""


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")


@pytest.fixture
def handler(keys, monkeypatch):
    fake = FakeLangfuseHandler()
    monkeypatch.setattr(tracing, "_callback_handler", lambda: fake)
    return fake


BASE = {"configurable": {"thread_id": "sim-1:user-1:chat"}, "metadata": {"source": "test"}}


# --- disabled: the app behaves exactly as without tracing ---

def test_without_keys_the_config_is_unchanged_and_langfuse_is_not_imported(monkeypatch):
    for name in [m for m in sys.modules if m == "langfuse" or m.startswith("langfuse.")]:
        monkeypatch.delitem(sys.modules, name)

    config = tracing.tracing_config("chat", "user-1", "sim-1:user-1", base=BASE)

    assert config == BASE and config is not BASE
    assert tracing.tracing_config("report") == {}
    assert not any(m == "langfuse" or m.startswith("langfuse.") for m in sys.modules)


def test_with_only_one_key_tracing_stays_off(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    assert tracing.tracing_config("chat", base=BASE) == BASE


# --- enabled ---

def test_with_keys_the_callback_run_name_and_metadata_are_added(handler):
    config = tracing.tracing_config("chat", "user-1", "sim-1:user-1", base=BASE)

    assert config["callbacks"] == [handler]
    assert config["run_name"] == "chat"
    assert config["configurable"] == {"thread_id": "sim-1:user-1:chat"}  # the chat thread is kept
    assert config["metadata"] == {
        "source": "test",
        "langfuse_trace_name": "chat",
        "langfuse_tags": ["chat"],
        "langfuse_user_id": "user-1",
        "langfuse_session_id": "sim-1:user-1",
    }


def test_no_secrets_in_the_metadata(handler):
    config = tracing.tracing_config("knowledge", "user-1", "knowledge:user-1")
    assert set(config["metadata"]) == {"langfuse_trace_name", "langfuse_tags", "langfuse_user_id", "langfuse_session_id"}
    assert "sk-test" not in str(config["metadata"])


def test_never_raises_when_langfuse_cannot_be_imported(keys, monkeypatch):
    monkeypatch.setitem(sys.modules, "langfuse.langchain", None)  # makes the import fail
    assert tracing.tracing_config("chat", "user-1", base=BASE) == BASE


def test_never_raises_when_the_handler_fails(keys, monkeypatch):
    def broken():
        raise RuntimeError("bad configuration")

    monkeypatch.setattr(tracing, "_callback_handler", broken)
    assert tracing.tracing_config("chat", base=BASE) == BASE


# --- nested graphs ---

def test_child_config_passes_only_the_tracing_handler_and_keeps_the_parent_run(keys):
    langfuse, stream, parent = FakeLangfuseHandler(), StreamHandler(), uuid4()
    manager = CallbackManager([langfuse, stream], [langfuse, stream], parent_run_id=parent)

    config = tracing.child_config({"callbacks": manager}, configurable={"thread_id": "explain"})

    assert config["configurable"] == {"thread_id": "explain"}
    assert config["callbacks"].handlers == [langfuse]
    assert config["callbacks"].parent_run_id == parent


def test_child_config_without_tracing_is_only_the_extra_config():
    manager = CallbackManager([StreamHandler()])
    assert tracing.child_config({"callbacks": manager}, configurable={"thread_id": "x"}) == {
        "configurable": {"thread_id": "x"}}
    assert tracing.child_config(None) == {}


class InnerState(TypedDict, total=False):
    messages: list


def test_explain_graph_runs_inside_the_chat_trace(handler, monkeypatch):
    inner = StateGraph(InnerState)
    inner.add_node("explain_node", lambda state: {"messages": [AIMessage(content="explained")]})
    inner.add_edge(START, "explain_node")
    inner.add_edge("explain_node", END)
    monkeypatch.setattr(chat_graph, "build_agent_graph", lambda *args: inner.compile())

    graph = chat_graph.build_conversation_graph(
        "sim-1", "user-1", llm=ScriptedRouter({"day 3": payload("explain_agent", day_number=3)}),
    )
    config = tracing.tracing_config("chat", "user-1", "sim-1:user-1",
                                    base={"configurable": {"thread_id": "t1"}})
    result = graph.invoke({"messages": [HumanMessage(content="Why did it buy on day 3?")],
                           "simulation_id": "sim-1"}, config=config)

    assert result["messages"][-1].content == "explained"
    assert "explain_agent" in handler.ancestors("explain_node")  # nested, not a separate trace
    assert handler.ancestors("explain_node")[-1] == "chat"


# --- flush ---

def test_flush_does_nothing_without_keys(monkeypatch):
    monkeypatch.setitem(sys.modules, "langfuse", None)  # any import would raise
    tracing.flush_tracing()


def test_flush_sends_pending_traces_and_never_raises(keys, monkeypatch):
    flushed = []

    class FakeLangfuse:
        @staticmethod
        def get_client():
            return type("Client", (), {"flush": lambda self: flushed.append(True)})()

    monkeypatch.setitem(sys.modules, "langfuse", FakeLangfuse)
    tracing.flush_tracing()
    assert flushed == [True]

    monkeypatch.setitem(sys.modules, "langfuse", None)
    tracing.flush_tracing()  # import fails: logged, not raised
