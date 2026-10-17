"""Knowledge (RAG) agent: LangGraph graph.

    START -> validate_intent -+-(question)--> retrieve -> grade -+-(sufficient)---> generate --+
                              |                                  |                             |
                              |                                  +-(insufficient)-> refuse ----+--> save_history -> END
                              +-(greeting / invalid)---------------------------------------------+

Conditional edges are plain functions that look at the state and return the NAME of the next node.
"""
from langgraph.graph import END, START, StateGraph

from app.agents.common.llm import get_chat_model
from app.agents.knowledge.nodes import make_nodes
from app.agents.knowledge.state import KnowledgeState


def _after_intent(state: KnowledgeState) -> str:
    return "retrieve" if state["intent"] == "question" else "save_history"


def _after_grade(state: KnowledgeState) -> str:
    return "generate" if state["sufficient"] else "refuse"


def build_knowledge_graph(
    llm=None,
    grader_llm=None,
    embed_query=None,
    search_chunks=None,
    save_turn=None,
    rewrite_llm=None,
):
    """Dependencies are injectable so the tests run without Ollama or Supabase."""
    if embed_query is None:
        from app.vectorstore.embeddings import embed_query as embed_query
    if search_chunks is None:
        from app.vectorstore.repository import search_chunks as search_chunks
    if save_turn is None:
        from app.modules.knowledge.history import save_turn as save_turn

    llm = llm or get_chat_model()
    grader_llm = grader_llm or llm
    rewrite_llm = rewrite_llm or grader_llm

    nodes = make_nodes(
    llm,
    grader_llm,
    embed_query,
    search_chunks,
    save_turn,
    rewrite_llm=rewrite_llm,)

    graph = StateGraph(KnowledgeState)

    for name, function in nodes.items():
        graph.add_node(name, function)

    graph.add_edge(START, "validate_intent")
    graph.add_conditional_edges("validate_intent", _after_intent, ["retrieve", "save_history"])
    graph.add_edge("retrieve", "grade")
    graph.add_conditional_edges("grade", _after_grade, ["generate", "refuse"])
    graph.add_edge("generate", "save_history")
    graph.add_edge("refuse", "save_history")
    graph.add_edge("save_history", END)

    return graph.compile()
