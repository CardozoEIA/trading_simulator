# app/services/agent/insights/test_insights.py
import json

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from app.services.agent.insights import graph as insights_graph
from app.services.agent.insights.facts import compute_highlights, largest_drawdown, round_trips
from app.services.agent.insights.verify import unverified_values

RUN = {
    "asset": "SPY", "start_date": "2023-01-02", "end_date": "2023-06-30", "initial_capital": 1000.0,
    "strategies": ["SMA"], "status": "STOPPED_BY_RISK", "stop_reason": "Max drawdown of 10% reached",
}
TRADES = [
    {"date": "2023-01-10", "type": "BUY", "price": 100.0, "quantity": 10},
    {"date": "2023-02-10", "type": "SELL", "price": 120.0, "quantity": 10},
    {"date": "2023-03-01", "type": "BUY", "price": 125.0, "quantity": 8},
    {"date": "2023-03-20", "type": "SELL", "price": 110.0, "quantity": 8},
]
EQUITY = [
    {"date": "2023-01-02", "portfolio_value": 1000.0},
    {"date": "2023-02-10", "portfolio_value": 1200.0},
    {"date": "2023-03-20", "portfolio_value": 1080.0},
]
PRICES = [{"date": "2023-01-02", "price": 100.0}, {"date": "2023-03-20", "price": 104.0}]


def by_kind(highlights):
    return {h["kind"]: h for h in highlights}


def test_round_trips_pair_buy_then_sell():
    trips = round_trips(TRADES)
    assert [(t.buy_date, t.sell_date) for t in trips] == [("2023-01-10", "2023-02-10"), ("2023-03-01", "2023-03-20")]
    assert [t.pnl for t in trips] == [200.0, -120.0]


def test_largest_drawdown_dates():
    dd = largest_drawdown(EQUITY)
    assert (round(dd.pct, 2), dd.peak_date, dd.trough_date) == (10.0, "2023-02-10", "2023-03-20")


def test_compute_highlights_finds_every_notable_point():
    h = by_kind(compute_highlights(RUN, TRADES, EQUITY, PRICES))
    assert set(h) == {"BUY_AND_HOLD", "RISK_STOP", "BEST_TRADE", "WORST_TRADE", "MAX_DRAWDOWN"}
    assert h["BUY_AND_HOLD"]["label"] == "Beat buy & hold by 4.00 pts"
    assert h["BEST_TRADE"]["label"] == "Best trade +$200.00"
    assert h["BEST_TRADE"]["dates"] == ["2023-01-10", "2023-02-10"]
    assert h["WORST_TRADE"]["label"] == "Worst trade -$120.00"
    assert h["MAX_DRAWDOWN"]["label"] == "Largest drop -10.00%"
    assert h["MAX_DRAWDOWN"]["dates"] == ["2023-02-10", "2023-03-20"]


def test_compute_highlights_quiet_run_has_no_trade_or_drop_highlights():
    run = {**RUN, "status": "FINISHED"}
    flat = [{"date": "2023-01-02", "portfolio_value": 1000.0}, {"date": "2023-01-03", "portfolio_value": 1000.0}]
    h = by_kind(compute_highlights(run, [], flat, []))
    assert h == {}


def test_verify_accepts_copied_values_and_rejects_invented_ones():
    facts = "Total return: 15.00%. Largest drawdown: 10.00% on 2023-03-20."
    assert unverified_values("The portfolio gained 15% and fell 10.00% on 2023-03-20.", facts) == []
    assert unverified_values("It gained 18.5% by 2023-05-01.", facts) == ["2023-05-01", "18.5"]


# --- graph with fake tools and a scripted model ---

HIGHLIGHTS = [
    {"kind": "BEST_TRADE", "label": "Best trade +$200.00", "tone": "positive", "dates": [],
     "facts": "Bought on 2023-01-10 at $100.00 and sold on 2023-02-10 at $120.00: result $200.00 (20.00%)."},
    {"kind": "MAX_DRAWDOWN", "label": "Largest drop -10.00%", "tone": "negative", "dates": [],
     "facts": "The largest drop was 10.00%, from 2023-02-10 to 2023-03-20."},
]


@tool
def fake_overview() -> str:
    """Fake overview."""
    return "Total return: 8.00%."


@tool
def fake_highlights() -> str:
    """Fake highlights."""
    return json.dumps(HIGHLIGHTS)


class ScriptedLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def invoke(self, _messages):
        self.calls += 1
        return AIMessage(content=json.dumps({"explanations": self.replies.pop(0)}))


def run_graph(monkeypatch, replies):
    monkeypatch.setattr(insights_graph, "build_insight_tools", lambda _sim: [fake_overview, fake_highlights])
    llm = ScriptedLLM(replies)
    result = insights_graph.build_insights_graph(llm=llm).invoke({"simulation_id": "sim-1"})
    return result, llm


GOOD_BEST = {"kind": "BEST_TRADE", "title": "Your best trade", "detail": "It made $200.00, a 20.00% gain."}
GOOD_DD = {"kind": "MAX_DRAWDOWN", "title": "The biggest drop", "detail": "The portfolio fell 10.00% by 2023-03-20."}


def test_graph_explains_every_highlight(monkeypatch):
    result, llm = run_graph(monkeypatch, [[GOOD_BEST, GOOD_DD]])
    assert set(result["explanations"]) == {"BEST_TRADE", "MAX_DRAWDOWN"}
    assert llm.calls == 1


def test_graph_retries_only_the_highlight_with_invented_values(monkeypatch):
    invented_dd = {**GOOD_DD, "detail": "The portfolio fell 25% in March."}
    result, llm = run_graph(monkeypatch, [[GOOD_BEST, invented_dd], [GOOD_DD]])
    assert llm.calls == 2
    assert result["explanations"]["MAX_DRAWDOWN"]["detail"] == GOOD_DD["detail"]
    assert result["explanations"]["BEST_TRADE"]["detail"] == GOOD_BEST["detail"]


def test_graph_drops_unverifiable_explanations_after_last_attempt(monkeypatch):
    invented = {**GOOD_DD, "detail": "It fell 42%."}
    result, llm = run_graph(monkeypatch, [[GOOD_BEST, invented], [invented]])
    assert llm.calls == insights_graph.MAX_ATTEMPTS
    assert set(result["explanations"]) == {"BEST_TRADE"}
