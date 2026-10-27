# app/modules/agent/service.py
from fastapi import HTTPException
from app.agents.common.tracing import tracing_config
from app.agents.explain.graph import build_agent_graph
from app.agents.explain.run import run_explanation
from app.modules.agent import traces


def explain_decision(simulation_id: str, user_id: str, date: str) -> dict:
    """The verified explanation of one decision, with the tools the agent called (US-31)."""
    graph = build_agent_graph(simulation_id, user_id)
    config = tracing_config(
        "explain", user_id, simulation_id,
        base={"configurable": {"thread_id": f"{simulation_id}:explain"}},
    )

    try:
        result = run_explanation(graph, date, config)
    except Exception:
        # El modelo local (Ollama) puede estar caído o no responder — no reventar con un 500 crudo
        raise HTTPException(
            status_code=503,
            detail="The explanation service is unavailable right now. Make sure the local model (Ollama) is running and try again."
        )

    traces.save_trace(user_id, simulation_id, "explain", date, result["text"], result["trace"], result["verification"])
    return {"explanation": result["text"], "trace": result["trace"], "verification": result["verification"]}
