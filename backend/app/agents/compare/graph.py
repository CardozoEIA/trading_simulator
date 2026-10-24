# app/agents/compare/graph.py
"""Comparison of two of a student's simulations (US-27).

    START -> fetch_a --+
                       +-> diff -> explain -> verify -> END
    START -> fetch_b --+             ^           |
                                     +-- retry --+   (values not in the facts, or promises)

The fetch nodes call the student-bound tools (ownership checked on every call);
diff is pure Python; the model only explains the diff and verify rejects any
number or date it cannot back with the facts.
"""
import json
import logging
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from app.agents.common.llm import get_chat_model
from app.agents.compare.diff import configuration_diff, diff_facts, metrics_diff, winner
from app.agents.compare.prompts import COMPARE_SYSTEM_PROMPT
from app.agents.compare.tools import build_compare_tools
from app.agents.insights.verify import makes_promises, unverified_values

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2


class CompareState(TypedDict, total=False):
    user_id: str
    simulation_a: str
    simulation_b: str
    slice_a: dict
    slice_b: dict
    configuration_diff: list[dict]
    metrics_diff: list[dict]
    winner: str                 # "a" | "b" | "tie" (by total return)
    facts: str
    draft: str                  # raw explanation from the model, before verification
    explanation: str | None     # verified explanation
    feedback: str | None
    attempts: int


def _parse(content: str) -> str:
    data = json.loads(content)
    if isinstance(data, dict):
        text = data.get("explanation")
        if not isinstance(text, str):
            text = next((v for v in data.values() if isinstance(v, str)), "")
        return text.strip()
    return ""


def build_compare_graph(llm=None):
    llm = llm or get_chat_model(format="json")

    def _slice(state: CompareState, simulation_id: str) -> dict:
        _, simulation_slice = build_compare_tools(state["user_id"])
        return json.loads(simulation_slice.invoke({"simulation_id": simulation_id}))

    def fetch_a(state: CompareState) -> CompareState:
        return {"slice_a": _slice(state, state["simulation_a"])}

    def fetch_b(state: CompareState) -> CompareState:
        return {"slice_b": _slice(state, state["simulation_b"])}

    def diff(state: CompareState) -> CompareState:
        a, b = state["slice_a"], state["slice_b"]
        configuration = configuration_diff(a["configuration"], b["configuration"])
        metrics = metrics_diff(a, b)
        best = winner(metrics)
        return {
            "configuration_diff": configuration,
            "metrics_diff": metrics,
            "winner": best,
            "facts": diff_facts(a, b, configuration, metrics, best),
            "explanation": None,
            "attempts": 0,
            "feedback": None,
        }

    def explain(state: CompareState) -> CompareState:
        request = f"Facts about the two simulations:\n{state['facts']}"
        if state.get("feedback"):
            request += f"\n\nYour previous answer was rejected: {state['feedback']}"
        response = llm.invoke([SystemMessage(content=COMPARE_SYSTEM_PROMPT), HumanMessage(content=request)])
        try:
            draft = _parse(response.content)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Compare model returned invalid JSON: %s", str(response.content)[:200])
            draft = ""
        return {"attempts": state.get("attempts", 0) + 1, "draft": draft}

    def verify(state: CompareState) -> CompareState:
        draft = state.get("draft") or ""
        if not draft:
            return {"feedback": "Write the explanation as JSON in the requested shape."}
        if makes_promises(draft):
            return {"feedback": "Do not talk about future results or guarantees."}
        bad = unverified_values(draft, state["facts"])
        if bad:
            return {"feedback": (
                f"these values are not in the facts: {', '.join(sorted(set(bad)))}. "
                "Use only numbers and dates copied exactly from the facts."
            )}
        return {"explanation": draft, "feedback": None}

    def after_verify(state: CompareState) -> str:
        if state.get("feedback") and state.get("attempts", 0) < MAX_ATTEMPTS:
            return "explain"
        return END

    graph = StateGraph(CompareState)
    graph.add_node("fetch_a", fetch_a)
    graph.add_node("fetch_b", fetch_b)
    graph.add_node("diff", diff)
    graph.add_node("explain", explain)
    graph.add_node("verify", verify)
    graph.add_edge(START, "fetch_a")
    graph.add_edge(START, "fetch_b")
    graph.add_edge(["fetch_a", "fetch_b"], "diff")
    graph.add_edge("diff", "explain")
    graph.add_edge("explain", "verify")
    graph.add_conditional_edges("verify", after_verify, ["explain", END])
    return graph.compile()
