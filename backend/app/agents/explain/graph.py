# app/agents/explain/graph.py
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langchain_ollama import ChatOllama
from app.agents.explain.tools import build_tools, strategy_reference
from app.agents.explain.prompts import SYSTEM_PROMPT
from app.agents.explain.verify import extract_trace, verify_answer


class ExplainState(MessagesState):
    # US-31: the answer after self-verification, and what the check found
    final_answer: str | None
    verification: dict | None


def route_after_agent(state: ExplainState) -> str:
    """Tool calls go to the tools; a finished draft goes to the verification step."""
    last = state["messages"][-1]
    return "tools" if getattr(last, "tool_calls", None) else "verify"



def build_agent_graph(simulation_id: str, user_id: str, llm=None, reference=None):
    tools = build_tools(simulation_id, user_id)
    llm = (llm or ChatOllama(model="qwen2.5:7b", temperature=0)).bind_tools(tools)
    reference = reference or (lambda: strategy_reference(simulation_id))

    def call_model(state: MessagesState):
        messages = state["messages"]
        if not any(getattr(m, "type", None) == "system" for m in messages):
            from langchain_core.messages import SystemMessage
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        response = llm.invoke(messages)
        
        return {"messages": [response]}

    def verify(state: ExplainState):
        """Reflection step: every date and number of the draft must come from a tool result."""
        messages = state["messages"]
        trace = extract_trace(messages)
        request = next((m.content for m in reversed(messages) if getattr(m, "type", None) == "human"), "")
        try:
            facts = reference()
        except Exception:
            facts = ""
        result = verify_answer(messages[-1].content, trace, request_text=request, reference_facts=facts)
        return {"final_answer": result.text, "verification": result.as_dict()}

    graph = StateGraph(ExplainState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.add_node("verify", verify)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "verify": "verify"})
    graph.add_edge("tools", "agent")
    graph.add_edge("verify", END)

    checkpointer = MemorySaver()  # v1: en memoria, se pierde al reiniciar el backend
    return graph.compile(checkpointer=checkpointer)