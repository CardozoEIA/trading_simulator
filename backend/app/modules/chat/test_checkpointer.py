"""Conversation memory in Postgres (US-25).

The first tests run anywhere. The last ones need a real Postgres, so they are skipped unless
TEST_DATABASE_URL is set (for example to the same URL as SUPABASE_DB_URL):

    $env:TEST_DATABASE_URL = "postgresql://..."
    pytest app/modules/chat/test_checkpointer.py -v
"""
import json
import os
import uuid
from types import SimpleNamespace

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.modules.chat import checkpointer
from app.services.agent.conversation import graph as graph_module
from app.services.agent.conversation.graph import build_conversation_graph

DATABASE_URL = os.getenv("TEST_DATABASE_URL")
needs_database = pytest.mark.skipif(not DATABASE_URL, reason="Set TEST_DATABASE_URL to run against Postgres")


# ---------- fallback behaviour (no database needed) ----------

def test_without_a_database_url_the_app_falls_back_to_memory(monkeypatch):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.setattr(checkpointer, "_checkpointer", None)

    assert isinstance(checkpointer.get_checkpointer(), MemorySaver)


def test_an_unreachable_database_does_not_stop_the_app(monkeypatch):
    def unreachable(db_url):
        raise ConnectionError("cannot reach the database")

    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://nobody@nowhere/none")
    monkeypatch.setattr(checkpointer, "_build_postgres_checkpointer", unreachable)
    monkeypatch.setattr(checkpointer, "_checkpointer", None)

    assert isinstance(checkpointer.get_checkpointer(), MemorySaver)


def test_the_checkpointer_is_created_once(monkeypatch):
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.setattr(checkpointer, "_checkpointer", None)

    assert checkpointer.get_checkpointer() is checkpointer.get_checkpointer()


# ---------- real Postgres ----------

class ScriptedRouter:
    def __init__(self, script):
        self.script = script

    def invoke(self, messages):
        text = messages[-1].content
        for fragment, payload in self.script.items():
            if fragment in text:
                return SimpleNamespace(content=json.dumps(payload))
        return SimpleNamespace(content=json.dumps({"next_step": "clarify", "message": "?"}))


def route(next_step, **fields):
    return {
        "next_step": next_step,
        "day_number": None,
        "offset": None,
        "date": None,
        "parameter": None,
        "value": None,
        "message": None,
        **fields,
    }


class FakeAgent:
    def invoke(self, state, config=None):
        return {"messages": [AIMessage(content="Explained: " + state["messages"][-1].content)]}


@pytest.fixture
def conversation(monkeypatch):
    dates = [f"2023-10-{day:02d}" for day in range(1, 31)]
    monkeypatch.setattr(graph_module, "load_decision_dates", lambda simulation_id: dates)
    monkeypatch.setattr(graph_module, "build_agent_graph", lambda *a, **k: FakeAgent())

    def build(saver):
        return build_conversation_graph(
            "sim-1",
            "user-1",
            llm=ScriptedRouter(
                {
                    "day 16": route("explain_agent", day_number=16),
                    "next day": route("explain_agent", offset=1),
                }
            ),
            chat_llm=GenericFakeChatModel(messages=iter([AIMessage(content="unused")])),
            checkpointer=saver,
        )

    return build


@pytest.fixture
def thread():
    """A throwaway thread id, removed from the database afterwards."""
    thread_id = f"test-{uuid.uuid4()}"
    yield thread_id

    saver = checkpointer._build_postgres_checkpointer(DATABASE_URL)
    saver.delete_thread(thread_id)


def ask(graph, thread_id, question):
    return graph.invoke(
        {"messages": [HumanMessage(content=question)], "simulation_id": "sim-1"},
        config={"configurable": {"thread_id": thread_id}},
    )


@needs_database
def test_the_conversation_survives_a_backend_restart(conversation, thread):
    first_process = checkpointer._build_postgres_checkpointer(DATABASE_URL)
    ask(conversation(first_process), thread, "Why did it sell on day 16?")

    # A new process: new connection pool, new graph, nothing kept in RAM.
    second_process = checkpointer._build_postgres_checkpointer(DATABASE_URL)
    result = ask(conversation(second_process), thread, "And the next day?")

    assert result["last_date_discussed"] == "2023-10-17"
    assert len(result["messages"]) == 4


@needs_database
def test_students_do_not_see_each_others_memory(conversation, thread):
    saver = checkpointer._build_postgres_checkpointer(DATABASE_URL)
    graph = conversation(saver)

    ask(graph, thread, "Why did it sell on day 16?")

    other_student = {"configurable": {"thread_id": f"{thread}-someone-else"}}

    assert graph.get_state(other_student).values == {}


@needs_database
def test_starting_a_new_conversation_erases_the_stored_memory(conversation, thread):
    saver = checkpointer._build_postgres_checkpointer(DATABASE_URL)
    graph = conversation(saver)

    ask(graph, thread, "Why did it sell on day 16?")
    saver.delete_thread(thread)

    fresh = checkpointer._build_postgres_checkpointer(DATABASE_URL)
    result = ask(conversation(fresh), thread, "And the next day?")

    assert result["next_step"] == "clarify"  # it no longer knows which day was discussed


@needs_database
def test_the_checkpoint_tables_are_closed_to_the_public_api():
    saver = checkpointer._build_postgres_checkpointer(DATABASE_URL)

    with saver.conn.connection() as connection:
        rows = connection.execute(
            "select tablename, rowsecurity from pg_tables where tablename = any(%s)",
            [list(checkpointer.CHECKPOINT_TABLES)],
        ).fetchall()

    assert {row["tablename"] for row in rows} == set(checkpointer.CHECKPOINT_TABLES)
    assert all(row["rowsecurity"] for row in rows)
