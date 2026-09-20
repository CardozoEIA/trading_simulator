# app/modules/agent/service.py
from langchain_core.messages import HumanMessage
from app.services.agent.graph import build_agent_graph


def explain_decision(simulation_id: str, user_id: str, date: str) -> str:
    graph = build_agent_graph(simulation_id, user_id)
    config = {"configurable": {"thread_id": f"{simulation_id}:explain"}}

    result = graph.invoke(
        {"messages": [HumanMessage(content=f"Explain the trading decision made on {date}.")]},
        config=config
    )
    return result["messages"][-1].content