# app/services/agent/insights/test_insights.py
import json

from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from app.services.agent.insights import graph as insights_graph
from app.services.agent.insights.facts import (
    buy_and_hold_text,
    drawdown_text,
    round_trips,
    trade_performance_text,
)
from app.services.agent.insights.verify import unverified_values

TRADES = [
    {"date": "2023-01-10", "type": "BUY", "price": 100.0, "quantity": 10},
    {"date": "2023-02-10", "type": "SELL", "price": 120.0, "quantity": 10},
    {"date": "2023-03-01", "type": "BUY", "price": 125.0, "quantity": 8},
    {"date": "2023-03-20", "type": "SELL", "price": 110.0, "quantity": 8},
    {"date": "2023-04-01", "type": "BUY", "price": 112.0, "quantity": 9},
]

EQUITY = [
    {"date": "2023-01-02", "portfolio_value": 1000.0},
    {"date": "2023-02-10", "portfolio_value": 1200.0},
    {"date": "2023-03-20", "portfolio_value": 1080.0},
    {"date": "2023-04-28", "portfolio_value": 1150.0},
]


def test_round_trips_pair_buy_then_sell():
    trips = round_trips(TRADES)
    assert [(t.buy_date, t.sell_date) for t in trips] == [("2023-01-10", "2023-02-10"), ("2023-03-01", "2023-03-20")]
    assert trips[0].pnl == 200.0
    assert trips[1].pnl == -120.0


def test_trade_performance_names_best_worst_and_open_position():
    text = trade_performance_text(TRADES)
    assert "Best round-trip: bought 2023-01-10" in text and "$200.00 (20.00%)" in text
    assert "Worst round-trip: bought 2023-03-01" in text and "-$120.00 (-12.00%)" in text
    assert "still open" in text


def test_trade_performance_without_trades():
    assert trade_performance_text([]) == "No trades were executed in this simulation."


def test_drawdown_reports_peak_and_trough_dates():
    text = drawdown_text(EQUITY, 1000.0)
    assert "Total return: 15.00%" in text
    assert "Largest drawdown: 10.00%, from the peak on 2023-02-10 to the low on 2023-03-20" in text


def test_buy_and_hold_comparison():
    prices = [{"date": "2023-01-02", "price": 100.0}, {"date": "2023-04-28", "price": 110.0}]
    text = buy_and_hold_text(prices, 1000.0, 1150.0)
    assert "would have returned 10.00%" in text
    assert "beat buy & hold by 5.00 percentage points" in text


def test_verify_accepts_copied_values_and_rejects_invented_ones():
    facts = "Total return: 15.00%. Largest drawdown: 10.00% on 2023-03-20."
    assert unverified_values("The portfolio gained 15% and fell 10.00% on 2023-03-20.", facts) == []
    assert unverified_values("It gained 18.5% by 2023-05-01.", facts) == ["2023-05-01", "18.5"]


# --- graph with fake tools and a scripted model ---

@tool
def fake_facts() -> str:
    """Fake facts."""
    return "Total return: 15.00%.\nLargest drawdown: 10.00%, from the peak on 2023-02-10 to the low on 2023-03-20."


class ScriptedLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def invoke(self, _messages):
        self.calls += 1
        return AIMessage(content=json.dumps({"insights": self.replies.pop(0)}))


def run_graph(monkeypatch, replies):
    monkeypatch.setattr(insights_graph, "build_insight_tools", lambda _sim: [fake_facts])
    llm = ScriptedLLM(replies)
    result = insights_graph.build_insights_graph(llm=llm).invoke({"simulation_id": "sim-1"})
    return result, llm


def test_graph_keeps_verified_insights(monkeypatch):
    good = [
        {"title": "Overall result", "detail": "The strategy returned 15.00%."},
        {"title": "Largest drop", "detail": "It fell 10.00% between 2023-02-10 and 2023-03-20."},
    ]
    result, llm = run_graph(monkeypatch, [good])
    assert result["insights"] == good
    assert llm.calls == 1


def test_graph_retries_when_values_are_invented(monkeypatch):
    invented = [{"title": "Result", "detail": "It returned 42%."}, {"title": "Drop", "detail": "It fell 3%."}]
    good = [
        {"title": "Overall result", "detail": "The strategy returned 15.00%."},
        {"title": "Largest drop", "detail": "It fell 10.00%."},
    ]
    result, llm = run_graph(monkeypatch, [invented, good])
    assert llm.calls == 2
    assert result["insights"] == good


def test_graph_drops_unverifiable_insights_after_last_attempt(monkeypatch):
    invented = [{"title": "Result", "detail": "It returned 42%."}]
    result, llm = run_graph(monkeypatch, [invented, invented])
    assert llm.calls == insights_graph.MAX_ATTEMPTS
    assert result["insights"] == []
