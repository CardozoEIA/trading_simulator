# app/services/agent/insights/graph.py
"""Event-triggered insights graph (US-26).

Entered when a simulation finishes (not by a user question):

    gather_facts -> write_insights -> verify -> END
                         ^                   |
                         +-- retry when it --+
                             used values not in the facts
"""
import json
import logging
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph

from app.services.agent.insights.prompts import INSIGHTS_SYSTEM_PROMPT
from app.services.agent.insights.tools import build_insight_tools
from app.services.agent.insights.verify import unverified_values

logger = logging.getLogger(__name__)

MODEL_NAME = "qwen2.5:7b"
MAX_ATTEMPTS = 2
MIN_INSIGHTS = 2
MAX_INSIGHTS = 5


class InsightsState(TypedDict, total=False):
    simulation_id: str
    facts: str
    insights: list[dict]
    feedback: str | None
    attempts: int


def _parse(content: str) -> list[dict]:
    data = json.loads(content)
    items = data.get("insights", []) if isinstance(data, dict) else data
    parsed = []
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict) and item.get("title") and item.get("detail"):
            parsed.append({"title": str(item["title"]).strip(), "detail": str(item["detail"]).strip()})
    return parsed


def build_insights_graph(llm=None):
    llm = llm or ChatOllama(model=MODEL_NAME, temperature=0, format="json")

    def gather_facts(state: InsightsState) -> InsightsState:
        tools = build_insight_tools(state["simulation_id"])
        sections = [f"[{t.name}]\n{t.invoke({})}" for t in tools]
        return {"facts": "\n\n".join(sections), "attempts": 0, "feedback": None}

    def write_insights(state: InsightsState) -> InsightsState:
        request = f"Simulation facts:\n\n{state['facts']}"
        if state.get("feedback"):
            request += f"\n\nYour previous answer was rejected: {state['feedback']}"
        response = llm.invoke([SystemMessage(content=INSIGHTS_SYSTEM_PROMPT), HumanMessage(content=request)])
        try:
            insights = _parse(response.content)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Insights model returned invalid JSON: %s", response.content[:200])
            insights = []
        return {"insights": insights, "attempts": state.get("attempts", 0) + 1}

    def verify(state: InsightsState) -> InsightsState:
        kept, problems = [], []
        for insight in state.get("insights", []):
            bad = unverified_values(f"{insight['title']} {insight['detail']}", state["facts"])
            if bad:
                problems.extend(bad)
            else:
                kept.append(insight)
        feedback = None
        if len(kept) < MIN_INSIGHTS:
            feedback = (
                f"these values are not in the facts: {', '.join(sorted(set(problems)))}. "
                if problems else "it did not contain valid insights in the requested JSON format. "
            ) + "Use only numbers and dates copied exactly from the facts."
        return {"insights": kept[:MAX_INSIGHTS], "feedback": feedback}

    def after_verify(state: InsightsState) -> str:
        if state.get("feedback") and state.get("attempts", 0) < MAX_ATTEMPTS:
            return "write_insights"
        return END

    graph = StateGraph(InsightsState)
    graph.add_node("gather_facts", gather_facts)
    graph.add_node("write_insights", write_insights)
    graph.add_node("verify", verify)
    graph.add_edge(START, "gather_facts")
    graph.add_edge("gather_facts", "write_insights")
    graph.add_edge("write_insights", "verify")
    graph.add_conditional_edges("verify", after_verify, ["write_insights", END])
    return graph.compile()
