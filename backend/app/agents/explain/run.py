# app/agents/explain/run.py
"""Runs the explain agent and returns the answer with its traceability record (US-31)."""
from langchain_core.messages import HumanMessage

from app.agents.explain.verify import extract_trace


def explanation_request(date: str) -> str:
    return f"Explain the trading decision made on {date}."


def run_explanation(graph, date: str, config: dict) -> dict:
    """{"text", "trace", "verification"}. `text` is the VERIFIED answer."""
    result = graph.invoke({"messages": [HumanMessage(content=explanation_request(date))]}, config=config)
    messages = result["messages"]
    return {
        "text": result.get("final_answer") or messages[-1].content,
        "trace": extract_trace(messages),
        "verification": result.get("verification"),
    }
