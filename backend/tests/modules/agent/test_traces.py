import pytest
from fastapi import HTTPException

from app.modules.agent import service, traces
from tests.fake_supabase import FakeSupabase

SIM = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
TRACE = [{"tool": "get_decision", "arguments": {"date": "2023-10-05"}, "result": "Action: BUY"}]
VERIFICATION = {"verified": True, "tools_called": 1, "removed": []}


@pytest.fixture
def db(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setattr(traces, "supabase", fake)
    return fake


def test_a_trace_is_saved_and_read_back_for_its_owner_only(db):
    traces.save_trace("user-1", SIM, "explain", "2023-10-05", "Bought.", TRACE, VERIFICATION)
    traces.save_trace("user-1", SIM, "chat", "2023-10-06", "Sold.", TRACE, VERIFICATION)
    assert [t["source"] for t in traces.get_traces(SIM, "user-1")] == ["chat", "explain"]  # newest first
    assert [t["date"] for t in traces.get_traces(SIM, "user-1", date="2023-10-05")] == ["2023-10-05"]
    assert traces.get_traces(SIM, "someone-else") == []


def test_long_results_are_cut(db):
    traces.save_trace("user-1", SIM, "explain", None, "x", [{"tool": "t", "arguments": {}, "result": "y" * 5000}], None)
    assert len(db.tables["agent_traces"][0]["tool_calls"][0]["result"]) == traces.MAX_RESULT_LENGTH


def test_a_failed_save_never_breaks_the_explanation(db):
    db.fail = True
    traces.save_trace("user-1", SIM, "explain", None, "x", TRACE, None)  # must not raise


def test_a_malformed_simulation_id_is_a_404(db):
    with pytest.raises(HTTPException) as error:
        traces.get_traces("nope", "user-1")
    assert error.value.status_code == 404


def test_explaining_returns_the_trace_and_stores_it(db, monkeypatch):
    monkeypatch.setattr(service, "build_agent_graph", lambda *a, **k: object())
    monkeypatch.setattr(service, "run_explanation",
                        lambda graph, date, config: {"text": "Bought.", "trace": TRACE, "verification": VERIFICATION})
    result = service.explain_decision(SIM, "user-1", "2023-10-05")
    assert result == {"explanation": "Bought.", "trace": TRACE, "verification": VERIFICATION}
    assert db.tables["agent_traces"][0]["answer"] == "Bought."


def test_an_unavailable_model_is_a_503(db, monkeypatch):
    def boom(graph, date, config):
        raise RuntimeError("ollama down")

    monkeypatch.setattr(service, "build_agent_graph", lambda *a, **k: object())
    monkeypatch.setattr(service, "run_explanation", boom)
    with pytest.raises(HTTPException) as error:
        service.explain_decision(SIM, "user-1", "2023-10-05")
    assert error.value.status_code == 503
