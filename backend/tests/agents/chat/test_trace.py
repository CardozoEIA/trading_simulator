"""US-31 in the conversation: an explanation answered in the chat carries its trace."""
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.chat import graph as graph_module
from app.modules.chat import service
from tests.agents.chat.test_conversation import DATES, ask, make_graph, offline, payload  # noqa: F401 (fixture)

TRACE = [{"tool": "get_decision", "arguments": {"date": DATES[4]}, "result": "Action: BUY"}]


class TracingAgent:
    def invoke(self, state, config=None):
        return {
            "messages": [
                HumanMessage(content=state["messages"][-1].content),
                AIMessage(content="", tool_calls=[{"name": "get_decision", "args": {"date": DATES[4]}, "id": "1"}]),
                ToolMessage(content="Action: BUY", tool_call_id="1", name="get_decision"),
                AIMessage(content="draft"),
            ],
            "final_answer": "Bought: Action BUY.",
            "verification": {"verified": True, "tools_called": 1, "removed": []},
        }


def test_a_chat_explanation_returns_its_verified_text_and_trace(monkeypatch):
    monkeypatch.setattr(graph_module, "build_agent_graph", lambda *a, **k: TracingAgent())
    graph = make_graph({"why": payload("explain_agent", day_number=5)})
    result = ask(graph, "why did it buy on day 5?")
    assert result["messages"][-1].content == "Bought: Action BUY."   # the verified text, not the draft
    assert result["trace"] == TRACE
    assert result["verification"]["verified"] is True


def test_the_reply_payload_exposes_the_trace_only_for_the_turn_that_made_it(monkeypatch):
    monkeypatch.setattr(graph_module, "build_agent_graph", lambda *a, **k: TracingAgent())
    graph = make_graph({"why": payload("explain_agent", day_number=5), "overview": payload("insights_agent")})
    config = {"configurable": {"thread_id": "t1"}}

    def turn(text):
        state = {"messages": [HumanMessage(content=text)], "simulation_id": "sim-1", "trace": None, "verification": None}
        return service._reply_payload(graph.invoke(state, config=config))

    explained = turn("why did it buy on day 5?")
    assert explained["trace"] == TRACE and explained["verification"]["verified"] is True

    later = turn("give me an overview")
    assert later["trace"] == [] and later["verification"] is None


def test_only_explanations_are_stored_as_traces(monkeypatch):
    saved = []
    monkeypatch.setattr(service.traces, "save_trace", lambda *args: saved.append(args))
    service._save_trace("u", "s", {"route": "insights_agent", "trace": TRACE, "reply": "x"})
    service._save_trace("u", "s", {"route": "explain_agent", "trace": [], "reply": "x"})
    service._save_trace("u", "s", {"route": "explain_agent", "trace": TRACE, "reply": "Bought", "date": DATES[4],
                                   "verification": {"verified": True}})
    assert saved == [("u", "s", "chat", DATES[4], "Bought", TRACE, {"verified": True})]
