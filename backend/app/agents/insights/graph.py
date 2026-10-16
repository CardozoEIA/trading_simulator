# app/agents/insights/graph.py
"""Event-triggered highlights graph (US-26).

Entered when a simulation finishes (not by a user question):

    gather_facts -> explain -> verify -> END
                      ^           |
                      +-- retry --+   (explanations that used values not in the facts)

gather_facts finds what is worth highlighting; the model only writes the
explanation of each highlight, and verify drops anything it cannot back with data.
"""
import json
import logging
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

from app.agents.insights.prompts import INSIGHTS_SYSTEM_PROMPT
from app.agents.insights.tools import build_insight_tools
from app.agents.insights.verify import unverified_values

logger = logging.getLogger(__name__)

MODEL_NAME = "qwen2.5:7b"
MAX_ATTEMPTS = 2


class InsightsState(TypedDict, total=False):
    simulation_id: str
    overview: str
    highlights: list[dict]
    drafts: list[dict]              # raw explanations from the model, before verification
    explanations: dict[str, dict]   # kind -> {"title", "detail"} (verified)
    feedback: str | None
    attempts: int


def _parse(content: str) -> list[dict]:
    data = json.loads(content)
    items = data.get("explanations", []) if isinstance(data, dict) else data
    return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []


def _pending(state: InsightsState) -> list[dict]:
    done = state.get("explanations") or {}
    return [h for h in state.get("highlights", []) if h["kind"] not in done]


def build_insights_graph(llm=None):
    llm = llm or ChatOllama(model=MODEL_NAME, temperature=0, format="json")

    def gather_facts(state: InsightsState) -> InsightsState:
        overview_tool, highlights_tool = build_insight_tools(state["simulation_id"])
        return {
            "overview": overview_tool.invoke({}),
            "highlights": json.loads(highlights_tool.invoke({})),
            "explanations": {},
            "attempts": 0,
            "feedback": None,
        }

    def explain(state: InsightsState) -> InsightsState:
        blocks = "\n\n".join(f"[{h['kind']}] {h['label']}\nFacts: {h['facts']}" for h in _pending(state))
        request = f"Simulation overview:\n{state['overview']}\n\nHighlights to explain:\n\n{blocks}"
        if state.get("feedback"):
            request += f"\n\nYour previous answer was rejected: {state['feedback']}"
        response = llm.invoke([SystemMessage(content=INSIGHTS_SYSTEM_PROMPT), HumanMessage(content=request)])
        try:
            drafts = _parse(response.content)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Insights model returned invalid JSON: %s", str(response.content)[:200])
            drafts = []
        return {"attempts": state.get("attempts", 0) + 1, "drafts": drafts}

    def verify(state: InsightsState) -> InsightsState:
        explanations = dict(state.get("explanations") or {})
        pending = {h["kind"]: h for h in _pending(state)}
        problems: list[str] = []
        for draft in state.get("drafts", []):
            kind = draft.get("kind")
            title, detail = str(draft.get("title", "")).strip(), str(draft.get("detail", "")).strip()
            if kind not in pending or not title or not detail:
                continue
            bad = unverified_values(f"{title} {detail}", f"{pending[kind]['facts']}\n{state['overview']}")
            if bad:
                problems.extend(bad)
            else:
                explanations[kind] = {"title": title, "detail": detail}

        missing = [k for k in pending if k not in explanations]
        feedback = None
        if missing:
            feedback = (
                f"these values are not in the facts: {', '.join(sorted(set(problems)))}. " if problems else ""
            ) + f"Explain {', '.join(missing)} using only numbers and dates copied exactly from the facts."
        return {"explanations": explanations, "feedback": feedback}

    def after_gather(state: InsightsState) -> str:
        return "explain" if state.get("highlights") else END

    def after_verify(state: InsightsState) -> str:
        if state.get("feedback") and state.get("attempts", 0) < MAX_ATTEMPTS:
            return "explain"
        return END

    graph = StateGraph(InsightsState)
    graph.add_node("gather_facts", gather_facts)
    graph.add_node("explain", explain)
    graph.add_node("verify", verify)
    graph.add_edge(START, "gather_facts")
    graph.add_conditional_edges("gather_facts", after_gather, ["explain", END])
    graph.add_edge("explain", "verify")
    graph.add_conditional_edges("verify", after_verify, ["explain", END])
    return graph.compile()
