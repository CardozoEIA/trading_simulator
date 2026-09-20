# app/services/agent/graph.py
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langchain_ollama import ChatOllama
from app.services.agent.tools import build_tools
from app.services.agent.prompts import SYSTEM_PROMPT



def build_agent_graph(simulation_id: str, user_id: str):
    tools = build_tools(simulation_id, user_id)
    llm = ChatOllama(model="qwen2.5:7b", temperature=0).bind_tools(tools)

    def call_model(state: MessagesState):
        messages = state["messages"]
        if not any(getattr(m, "type", None) == "system" for m in messages):
            from langchain_core.messages import SystemMessage
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        response = llm.invoke(messages)
        
        return {"messages": [response]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")

    checkpointer = MemorySaver()  # v1: en memoria, se pierde al reiniciar el backend
    return graph.compile(checkpointer=checkpointer)