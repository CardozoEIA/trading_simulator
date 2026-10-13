import json
import logging

from fastapi import HTTPException
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage

from app.modules.chat import history, memory
from app.modules.chat.checkpointer import get_checkpointer
from app.modules.insights.service import _ensure_owner
from app.services.agent.conversation.followups import suggest_followups
from app.services.agent.conversation.graph import (
    build_conversation_graph,
)

logger = logging.getLogger(__name__)

UNAVAILABLE = (
    "The assistant is not available right now. "
    "Please try again in a moment."
)

SEED_LIMIT = 10  # past messages loaded back into the graph after a server restart


def _thread_id(simulation_id: str, user_id: str) -> str:
    return f"{simulation_id}:{user_id}:chat"


def _config(simulation_id: str, user_id: str) -> dict:
    return {"configurable": {"thread_id": _thread_id(simulation_id, user_id)}}


def _memory_lookup(user_id: str, simulation_id: str):
    """Lets the graph fetch the relevant earlier turns, only when a node needs them."""
    return lambda question: memory.build_memory_context(user_id, simulation_id, question)


def _to_message(row: dict):
    if row["role"] == "user":
        return HumanMessage(content=row["content"])
    return AIMessage(content=row["content"])


def _build_input(graph, config: dict, simulation_id: str, user_id: str, message: str) -> dict:
    """Graph input for this turn. After a restart the in-memory thread is empty: reload it from the database."""

    payload = {
        "messages": [HumanMessage(content=message)],
        "simulation_id": simulation_id,
    }

    snapshot = graph.get_state(config)

    if (snapshot.values or {}).get("messages"):
        return payload

    past = history.load_history(user_id, simulation_id, limit=SEED_LIMIT)

    if not past:
        return payload

    payload["messages"] = [_to_message(row) for row in past] + payload["messages"]

    last_date = next((row["date"] for row in reversed(past) if row.get("date")), None)

    if last_date:
        payload["last_date_discussed"] = last_date

    return payload


def _reply_payload(result: dict) -> dict:
    route = result.get("next_step")
    date = result.get("last_date_discussed")

    return {
        "reply": result["messages"][-1].content,
        "route": route,
        "date": date,
        "suggestions": suggest_followups(route, date),
        "proposed_change": result.get("proposed_change"),
    }


def chat(
    simulation_id: str,
    user_id: str,
    message: str,
) -> dict:

    # Outside the try block on purpose: its 404 must not become a 503.
    _ensure_owner(simulation_id, user_id)

    config = _config(simulation_id, user_id)

    try:
        graph = build_conversation_graph(
            simulation_id,
            user_id,
            checkpointer=get_checkpointer(),
            memory_lookup=_memory_lookup(user_id, simulation_id),
        )

        result = graph.invoke(
            _build_input(graph, config, simulation_id, user_id, message),
            config=config,
        )

        payload = _reply_payload(result)
    except Exception:
        logger.exception("Conversation graph failed")
        raise HTTPException(status_code=503, detail=UNAVAILABLE)

    memory.remember_turn(user_id, simulation_id, message, payload)

    return payload


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _token_text(chunk, metadata: dict) -> str:
    """Text worth showing while the answer is being written. Router JSON and tool calls are skipped."""

    if not isinstance(chunk, AIMessageChunk):
        return ""

    if (metadata or {}).get("langgraph_node") == "supervisor":
        return ""

    if chunk.tool_call_chunks or not isinstance(chunk.content, str):
        return ""

    return chunk.content


def chat_stream(
    simulation_id: str,
    user_id: str,
    message: str,
):
    """Server-sent events: `token` while the model writes, then `done` (full reply) or `error`."""

    # Runs before the response starts, so a foreign simulation is a real 404.
    _ensure_owner(simulation_id, user_id)

    config = _config(simulation_id, user_id)

    def events():
        final = None

        try:
            graph = build_conversation_graph(
                simulation_id,
                user_id,
                checkpointer=get_checkpointer(),
                memory_lookup=_memory_lookup(user_id, simulation_id),
            )

            graph_input = _build_input(graph, config, simulation_id, user_id, message)

            for mode, data in graph.stream(
                graph_input,
                config=config,
                stream_mode=["messages", "values"],
            ):
                if mode == "messages":
                    chunk, metadata = data
                    text = _token_text(chunk, metadata)

                    if text:
                        yield _sse("token", {"text": text})

                elif mode == "values":
                    final = data

            if not final or not final.get("messages"):
                raise RuntimeError("The conversation graph returned no messages")

            payload = _reply_payload(final)
        except Exception:
            logger.exception("Conversation stream failed")
            yield _sse("error", {"detail": UNAVAILABLE})
            return

        memory.remember_turn(user_id, simulation_id, message, payload)

        yield _sse("done", payload)

    return events()


def get_history(simulation_id: str, user_id: str) -> dict:
    _ensure_owner(simulation_id, user_id)

    rows = history.load_history(user_id, simulation_id)

    last_answer = next((row for row in reversed(rows) if row["role"] == "assistant"), None)

    return {
        "messages": rows,
        "suggestions": suggest_followups(
            last_answer["route"] if last_answer else None,
            last_answer["date"] if last_answer else None,
        ),
    }


def reset_conversation(simulation_id: str, user_id: str) -> None:
    _ensure_owner(simulation_id, user_id)

    history.clear_history(user_id, simulation_id)

    try:
        get_checkpointer().delete_thread(_thread_id(simulation_id, user_id))
    except Exception:
        logger.exception("Could not clear the in-memory conversation")