import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_ollama import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.common.tracing import child_config
from app.agents.explain.graph import build_agent_graph
from app.agents.chat.support.dates import (
    load_decision_dates,
    resolve_date,
)
from app.agents.chat.prompts import build_conceptual_prompt
from app.agents.chat.support.comparisons import resolve_comparison
from app.agents.chat.support.proposals import (
    build_proposal,
    proposal_message,
)
from app.agents.chat.routing.router import (
    FALLBACK_MESSAGE,
    classify_question,
)
from app.agents.chat.state import SupervisorState
from app.agents.compare.tools import list_my_simulations
from app.agents.chat.tools import (
    buy_and_hold_comparison,
    compare_simulations_text,
    current_risk_values,
    summarize_simulation,
)

logger = logging.getLogger(__name__)

MODEL_NAME = "qwen2.5:7b"
OLLAMA_TIMEOUT_SECONDS = 60


def build_conversation_graph(
    simulation_id: str,
    user_id: str,
    llm=None,
    chat_llm=None,
    checkpointer=None,
    memory_lookup=None,
):
    # Router model: JSON only. A slow Ollama fails after OLLAMA_TIMEOUT_SECONDS instead of hanging.
    llm = llm or ChatOllama(
        model=MODEL_NAME,
        temperature=0,
        format="json",
        client_kwargs={"timeout": OLLAMA_TIMEOUT_SECONDS},
    )

    # Answer model for conceptual questions: free text, so it can stream token by token.
    chat_llm = chat_llm or ChatOllama(
        model=MODEL_NAME,
        temperature=0,
        client_kwargs={"timeout": OLLAMA_TIMEOUT_SECONDS},
    )

    def supervisor(state: SupervisorState) -> SupervisorState:

        question = state["messages"][-1].content
        last_date = state.get("last_date_discussed")

        decision = classify_question(llm, question, last_date)

        next_step = decision["next_step"]
        message = decision["message"]
        selected_date = None
        proposal = None
        compare_with = None

        if next_step == "explain_agent":
            date = decision["date"]

            if (
                isinstance(date, str)
                and len(date) >= 4
                and date[:4].isdigit()
                and date[:4] not in question
            ):
                next_step = "clarify"
                message = "Which year do you mean?"

            else:
                resolved, error = resolve_date(
                    dates=load_decision_dates(simulation_id),
                    last_date=last_date,
                    day_number=decision["day_number"],
                    offset=decision["offset"],
                    date=date,
                )

                if error:
                    next_step = "clarify"
                    message = error
                else:
                    selected_date = resolved

        elif next_step == "propose_change":
            try:
                current = current_risk_values(simulation_id)
            except Exception:
                logger.exception("Could not load the current risk limits")
                current = None

            proposal, error = build_proposal(
                decision["parameter"],
                decision["value"],
                current,
            )

            if error:
                next_step = "clarify"
                message = error

        elif next_step == "compare":
            try:
                history = list_my_simulations(user_id)
            except Exception:
                logger.exception("Could not load the simulation history")
                history = None

            if history is None:
                next_step = "clarify"
                message = "I cannot load your simulations right now. Please try again."
            else:
                compare_with, error = resolve_comparison(
                    history,
                    simulation_id,
                    decision["compare_with"],
                    decision["simulation_number"],
                )

                if error:
                    next_step = "clarify"
                    message = error

        if next_step == "explain_agent":
            return {
                "next_step": next_step,
                "last_date_discussed": selected_date,
                "proposed_change": None,
            }

        if next_step == "propose_change":
            return {
                "next_step": next_step,
                "proposed_change": proposal,
                "messages": [AIMessage(content=proposal_message(proposal))],
            }

        if next_step == "compare":
            return {
                "next_step": next_step,
                "proposed_change": None,
                "compare_with": compare_with,
            }

        if next_step == "clarify":
            return {
                "next_step": next_step,
                "proposed_change": None,
                "messages": [
                    AIMessage(content=message or FALLBACK_MESSAGE)
                ],
            }

        return {
            "next_step": next_step,
            "proposed_change": None,
        }

    def explain_agent(state: SupervisorState, config: RunnableConfig) -> SupervisorState:

        date = state["last_date_discussed"]

        graph = build_agent_graph(simulation_id, user_id)

        # Keeps its own thread; with tracing on, it also appears inside this conversation's trace.
        explain_config = child_config(
            config,
            configurable={"thread_id": f"{simulation_id}:conversation_explain"},
        )

        try:
            result = graph.invoke(
                {
                    "messages": [
                        HumanMessage(
                            content=f"Explain the trading decision made on {date}."
                        )
                    ]
                },
                config=explain_config,
            )

            return {
                "messages": [
                    AIMessage(content=result["messages"][-1].content)
                ]
            }

        except Exception:
            logger.exception("explain_agent failed")

            return {
                "messages": [
                    AIMessage(
                        content=(
                            "The explanation service is unavailable right now. "
                            "Please make sure Ollama is running and try again."
                        )
                    )
                ]
            }

    def insights_agent(state: SupervisorState) -> SupervisorState:

        try:
            return {
                "messages": [
                    AIMessage(content=summarize_simulation(simulation_id))
                ]
            }

        except Exception:
            logger.exception("insights_agent failed")

            return {
                "messages": [
                    AIMessage(
                        content=(
                            "The simulation summary is unavailable right now. "
                            "Please try again later."
                        )
                    )
                ]
            }

    def answer(state: SupervisorState) -> SupervisorState:

        try:
            return {
                "messages": [
                    AIMessage(content=buy_and_hold_comparison(simulation_id))
                ]
            }

        except Exception:
            logger.exception("answer failed")

            return {
                "messages": [
                    AIMessage(
                        content=(
                            "The buy and hold comparison "
                            "is unavailable right now. "
                            "Please try again later."
                        )
                    )
                ]
            }

    def compare_agent(state: SupervisorState, config: RunnableConfig) -> SupervisorState:

        try:
            return {
                "messages": [
                    AIMessage(
                        content=compare_simulations_text(
                            simulation_id, state["compare_with"], user_id,
                            config=child_config(config),
                        )
                    )
                ]
            }

        except Exception:
            logger.exception("compare_agent failed")

            return {
                "messages": [
                    AIMessage(
                        content=(
                            "The comparison is unavailable right now. "
                            "Please make sure Ollama is running and try again."
                        )
                    )
                ]
            }

    def conceptual_agent(state: SupervisorState) -> SupervisorState:

        question = state["messages"][-1].content

        # Long conversations: only the earlier turns relevant to this question are shown to the model.
        memory_context = None

        if memory_lookup is not None:
            try:
                memory_context = memory_lookup(question)
            except Exception:
                logger.exception("Memory lookup failed")

        try:
            response = chat_llm.invoke(
                [
                    SystemMessage(content=build_conceptual_prompt(memory_context)),
                    HumanMessage(content=question),
                ]
            )

            text = (response.content or "").strip()

            return {
                "messages": [
                    AIMessage(
                        content=text
                        or "I could not put together an answer. Could you rephrase the question?"
                    )
                ]
            }

        except Exception:
            logger.exception("conceptual_agent failed")

            return {
                "messages": [
                    AIMessage(
                        content=(
                            "I cannot answer that right now. "
                            "Please make sure Ollama is running and try again."
                        )
                    )
                ]
            }

    def route(state: SupervisorState):
        return state["next_step"]

    graph = StateGraph(SupervisorState)

    graph.add_node("supervisor", supervisor)
    graph.add_node("explain_agent", explain_agent)
    graph.add_node("insights_agent", insights_agent)
    graph.add_node("answer", answer)
    graph.add_node("conceptual_agent", conceptual_agent)
    graph.add_node("compare_agent", compare_agent)

    graph.add_edge(START, "supervisor")

    graph.add_conditional_edges(
        "supervisor",
        route,
        {
            "explain_agent": "explain_agent",
            "insights_agent": "insights_agent",
            "answer": "answer",
            "conceptual": "conceptual_agent",
            "compare": "compare_agent",
            "propose_change": END,
            "clarify": END,
        },
    )

    graph.add_edge("explain_agent", END)
    graph.add_edge("insights_agent", END)
    graph.add_edge("answer", END)
    graph.add_edge("conceptual_agent", END)
    graph.add_edge("compare_agent", END)

    return graph.compile(checkpointer=checkpointer or MemorySaver())