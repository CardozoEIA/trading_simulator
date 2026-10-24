# tests/agents/report/test_report.py
import json

from langchain_core.messages import AIMessage

from app.agents.insights.facts import compute_highlights
from app.agents.insights.verify import unverified_values
from app.agents.report import graph as report_graph
from app.agents.report.facts import DISCLAIMER, build_sections
from app.agents.report.render import NO_NARRATIVE, render_markdown

RUN = {
    "asset": "SPY", "start_date": "2023-01-02", "end_date": "2023-06-30", "initial_capital": 1000.0,
    "strategies": ["SMA"], "status": "FINISHED", "stop_reason": None,
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
    {"date": "2023-06-30", "portfolio_value": 1080.0},
]
PRICES = [{"date": "2023-01-02", "price": 100.0}, {"date": "2023-06-30", "price": 104.0}]

DATA = {
    "simulation": {"id": "sim-1", "configuration_id": "cfg-1", "status": "FINISHED", "stop_reason": None},
    "configuration": {
        "asset": "SPY", "start_date": "2023-01-02", "end_date": "2023-06-30", "initial_capital": 1000.0,
        "strategies": ["SMA"],
        "risk": {"stop_loss_percentage": 5.0, "max_position_size": 50.0, "max_drawdown": 20.0},
        "benchmark": {"initial_capital": 1000.0, "final_capital": 1040.0, "profit_loss": 40.0, "total_return_pct": 4.0},
    },
    "results": {"final_capital": 1080.0, "profit_loss": 80.0, "total_return_pct": 8.0},
    "metrics": {
        "total_return_pct": 8.0, "sharpe_ratio": 1.234, "max_drawdown_pct": 10.0, "win_rate": 50.0,
        "profit_factor": 1.6667, "total_trades": 2, "winning_trades": 1,
    },
    "trades": TRADES,
    "highlights": compute_highlights(RUN, TRADES, EQUITY, PRICES),
}


def by_key(sections):
    return {s["key"]: s for s in sections}


def rows(section):
    return {r["label"]: r["value"] for r in section["rows"]}


# --- structure built by code ---

def test_sections_are_fixed_and_in_order():
    keys = [s["key"] for s in build_sections(DATA)]
    assert keys == ["setup", "performance", "key_decisions", "benchmark", "disclaimer"]


def test_section_figures_match_the_raw_simulation_data():
    s = by_key(build_sections(DATA))
    assert rows(s["setup"]) == {
        "Asset": "SPY", "Period": "2023-01-02 to 2023-06-30", "Strategies": "SMA", "Initial capital": "$1,000.00",
        "Stop-loss": "5.00%", "Max position size": "50.00%", "Max drawdown limit": "20.00%",
    }
    perf = rows(s["performance"])
    assert perf["Final value"] == "$1,080.00"
    assert perf["Total return"] == "+8.00%"
    assert perf["Sharpe ratio"] == "1.23"
    assert perf["Profit factor"] == "1.67"
    assert perf["Winning trades"] == "1/2"

    decisions = s["key_decisions"]
    assert decisions["table"]["rows"] == [
        ["2023-01-10", "2023-02-10", "$100.00", "$120.00", "$200.00", "+20.00%"],
        ["2023-03-01", "2023-03-20", "$125.00", "$110.00", "-$120.00", "-12.00%"],
    ]
    assert "Best completed trade out of 2" in decisions["facts"]

    bench = rows(s["benchmark"])
    assert bench["Buy & hold return"] == "+4.00%"
    assert bench["Difference"] == "Beat by 4.00 pts"


def test_open_position_and_missing_benchmark_are_reported_without_inventing():
    data = {
        **DATA,
        "trades": TRADES + [{"date": "2023-04-03", "type": "BUY", "price": 105.0, "quantity": 9}],
        "configuration": {**DATA["configuration"], "benchmark": None},
    }
    s = by_key(build_sections(data))
    assert "still open" in s["key_decisions"]["note"]
    assert rows(s["benchmark"])["Buy & hold return"] == "n/a"
    assert "not available" in s["benchmark"]["facts"]


def test_disclaimer_is_fixed_text_and_not_a_guarantee():
    disclaimer = by_key(build_sections(DATA))["disclaimer"]
    assert disclaimer["narrative"] == DISCLAIMER
    assert "not a guarantee of future results" in DISCLAIMER


def test_markdown_contains_every_section_and_table():
    sections = build_sections(DATA)
    md = render_markdown("Simulation report: SPY", "2026-10-24 10:00 UTC", "sim-1", sections)
    for title in ("## Setup", "## Performance", "## Key decisions", "## Benchmark", "## Disclaimer"):
        assert title in md
    assert "| 2023-01-10 | 2023-02-10 | $100.00 | $120.00 | $200.00 | +20.00% |" in md
    assert NO_NARRATIVE in md  # no narratives yet: the figures still render


# --- graph with a scripted model ---

class ScriptedLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def invoke(self, _messages):
        self.calls += 1
        return AIMessage(content=json.dumps({"sections": self.replies.pop(0)}))


GOOD = [
    {"key": "setup", "narrative": "You tested the SMA strategy on SPY from 2023-01-02 to 2023-06-30 with $1,000.00."},
    {"key": "performance", "narrative": "The portfolio ended at $1,080.00, a total return of 8.00%."},
    {"key": "key_decisions", "narrative": "Of the 2 completed trades, the best one made $200.00."},
    {"key": "benchmark", "narrative": "Buy & hold returned 4.00%, so the strategy beat it by 4.00 percentage points."},
]


def run_graph(replies):
    llm = ScriptedLLM(replies)
    result = report_graph.build_report_graph(llm=llm).invoke({"data": DATA})
    return result, llm


def test_graph_writes_a_narrative_per_section(monkeypatch):
    result, llm = run_graph([GOOD])
    assert set(result["narratives"]) == {"setup", "performance", "key_decisions", "benchmark"}
    assert llm.calls == 1


def test_every_number_in_the_narratives_exists_in_the_facts():
    result, _ = run_graph([GOOD])
    facts = "\n".join(s["facts"] for s in result["sections"])
    for text in result["narratives"].values():
        assert unverified_values(text, facts) == []


def test_fabricated_number_is_caught_and_retried_once():
    invented = {"key": "benchmark", "narrative": "Buy & hold returned 6.75%, the strategy did better."}
    result, llm = run_graph([[*GOOD[:3], invented], [GOOD[3]]])
    assert llm.calls == 2
    assert result["narratives"]["benchmark"] == GOOD[3]["narrative"]


def test_unverifiable_narrative_is_dropped_after_the_retry():
    invented = {"key": "performance", "narrative": "The portfolio grew 42% in March."}
    result, llm = run_graph([[GOOD[0], invented, *GOOD[2:]], [invented]])
    assert llm.calls == report_graph.MAX_ATTEMPTS
    assert "performance" not in result["narratives"]
    assert set(result["narratives"]) == {"setup", "key_decisions", "benchmark"}


def test_promises_about_future_results_are_rejected():
    promise = {"key": "performance", "narrative": "This strategy will keep earning 8.00% and is guaranteed to work."}
    result, llm = run_graph([[GOOD[0], promise, *GOOD[2:]], [GOOD[1]]])
    assert llm.calls == 2
    assert result["narratives"]["performance"] == GOOD[1]["narrative"]


def test_written_out_dates_are_checked_as_dates():
    written = {"key": "setup", "narrative": "You tested SMA on SPY from January 2, 2023 to 30 June 2023."}
    result, llm = run_graph([[written, *GOOD[1:]]])
    assert llm.calls == 1
    assert result["narratives"]["setup"] == written["narrative"]

    wrong = {"key": "setup", "narrative": "You tested SMA on SPY from March 5, 2023."}
    result, _ = run_graph([[wrong, *GOOD[1:]], [wrong]])
    assert "setup" not in result["narratives"]


def test_misspelled_narrative_key_is_still_read():
    typo = {"key": "benchmark", "narmative": GOOD[3]["narrative"]}
    result, llm = run_graph([[*GOOD[:3], typo]])
    assert llm.calls == 1
    assert result["narratives"]["benchmark"] == GOOD[3]["narrative"]


def test_invalid_json_from_the_model_is_retried():
    class BrokenThenGood(ScriptedLLM):
        def invoke(self, messages):
            if self.calls == 0:
                self.calls += 1
                return AIMessage(content="not json")
            return super().invoke(messages)

    llm = BrokenThenGood([GOOD])
    result = report_graph.build_report_graph(llm=llm).invoke({"data": DATA})
    assert llm.calls == 2
    assert len(result["narratives"]) == 4
