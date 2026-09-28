# app/modules/agent/service.py
from fastapi import HTTPException
from langchain_core.messages import HumanMessage
from app.services.agent.graph import build_agent_graph


def explain_decision(simulation_id: str, user_id: str, date: str) -> str:
    graph = build_agent_graph(simulation_id, user_id)
    config = {"configurable": {"thread_id": f"{simulation_id}:explain"}}

    try:
        result = graph.invoke(
            {"messages": [HumanMessage(content=f"Explain the trading decision made on {date}.")]},
            config=config
        )
    except Exception:
        # El modelo local (Ollama) puede estar caído o no responder — no reventar con un 500 crudo
        raise HTTPException(
            status_code=503,
            detail="The explanation service is unavailable right now. Make sure the local model (Ollama) is running and try again."
        )
    return result["messages"][-1].content