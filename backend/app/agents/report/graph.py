# app/agents/report/graph.py
"""Simulation report graph (US-32).

    gather_facts -> write -> verify -> END
                      ^         |
                      +- retry -+   (narratives with values not in the facts, or promises)

gather_facts builds the fixed sections from the recorded data; the model only writes
a short narrative per section, and verify drops anything it cannot back with data.
"""
import json
import logging
import re
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from app.agents.common.llm import get_chat_model
from app.agents.insights.verify import unverified_values
from app.agents.report.facts import NARRATED_SECTIONS, build_sections
from app.agents.report.prompts import REPORT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2

# results of a past backtest must never read as a promise about the future
FORWARD_LOOKING_RE = re.compile(
    r"\b(guarantee\w*|promis\w*|will (?:always|continue|keep|make|earn|beat|outperform)|"
    r"you should (?:buy|sell|invest))\b",
    re.IGNORECASE,
)


class ReportState(TypedDict, total=False):
    data: dict                   # recorded simulation data (see tools.load_report_data)
    sections: list[dict]
    drafts: list[dict]           # raw narratives from the model, before verification
    narratives: dict[str, str]   # section key -> verified narrative
    feedback: str | None
    attempts: int


def _parse(content: str) -> list[dict]:
    data = json.loads(content)
    items = data.get("sections", []) if isinstance(data, dict) else data
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


def _pending(state: ReportState) -> list[dict]:
    done = state.get("narratives") or {}
    return [s for s in state.get("sections", []) if s["key"] in NARRATED_SECTIONS and s["key"] not in done]


def _context(state: ReportState) -> str:
    """The setup facts (asset, period) may be mentioned in any section."""
    return next((s["facts"] for s in state.get("sections", []) if s["key"] == "setup"), "")


def build_report_graph(llm=None):
    llm = llm or get_chat_model(format="json")

    def gather_facts(state: ReportState) -> ReportState:
        return {
            "sections": build_sections(state["data"]),
            "narratives": {},
            "attempts": 0,
            "feedback": None,
        }

    def write(state: ReportState) -> ReportState:
        blocks = "\n\n".join(f"[{s['key']}] {s['title']}\nFacts: {s['facts']}" for s in _pending(state))
        request = f"Sections to narrate:\n\n{blocks}"
        if state.get("feedback"):
            request += f"\n\nYour previous answer was rejected: {state['feedback']}"
        response = llm.invoke([SystemMessage(content=REPORT_SYSTEM_PROMPT), HumanMessage(content=request)])
        try:
            drafts = _parse(response.content)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Report model returned invalid JSON: %s", str(response.content)[:200])
            drafts = []
        return {"attempts": state.get("attempts", 0) + 1, "drafts": drafts}

    def verify(state: ReportState) -> ReportState:
        narratives = dict(state.get("narratives") or {})
        pending = {s["key"]: s for s in _pending(state)}
        problems: list[str] = []
        promises = False
        for draft in state.get("drafts", []):
            key, text = draft.get("key"), str(draft.get("narrative", "")).strip()
            if key not in pending or not text:
                continue
            bad = unverified_values(text, f"{pending[key]['facts']}\n{_context(state)}")
            if FORWARD_LOOKING_RE.search(text):
                promises = True
            elif bad:
                problems.extend(bad)
            else:
                narratives[key] = text

        missing = [k for k in pending if k not in narratives]
        feedback = None
        if missing:
            feedback = (
                (f"these values are not in the facts: {', '.join(sorted(set(problems)))}. " if problems else "")
                + ("Do not talk about future results or guarantees. " if promises else "")
                + f"Write {', '.join(missing)} using only numbers and dates copied exactly from the facts."
            )
        return {"narratives": narratives, "feedback": feedback}

    def after_verify(state: ReportState) -> str:
        if state.get("feedback") and state.get("attempts", 0) < MAX_ATTEMPTS:
            return "write"
        return END

    graph = StateGraph(ReportState)
    graph.add_node("gather_facts", gather_facts)
    graph.add_node("write", write)
    graph.add_node("verify", verify)
    graph.add_edge(START, "gather_facts")
    graph.add_edge("gather_facts", "write")
    graph.add_edge("write", "verify")
    graph.add_conditional_edges("verify", after_verify, ["write", END])
    return graph.compile()
