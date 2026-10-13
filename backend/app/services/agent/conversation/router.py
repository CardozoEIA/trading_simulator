import json
import math

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.agent.conversation.prompts import SUPERVISOR_SYSTEM_PROMPT

VALID_ROUTES = {
    "explain_agent",
    "insights_agent",
    "answer",
    "conceptual",
    "propose_change",
    "clarify",
}

FALLBACK_MESSAGE = "I didn't understand that, could you rephrase?"


def parse_int(value):
    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, str) and value.isdigit():
        return int(value)

    return None


def parse_number(value):
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value.strip().rstrip("%"))
        except ValueError:
            return None
    else:
        return None

    if math.isnan(number) or math.isinf(number):
        return None

    return number


def _fallback(message: str = FALLBACK_MESSAGE) -> dict:
    return {
        "next_step": "clarify",
        "day_number": None,
        "offset": None,
        "date": None,
        "parameter": None,
        "value": None,
        "message": message,
    }


def classify_question(llm, question: str, last_date: str | None) -> dict:
    """Ask the model for a route and validate its JSON. Never raises on bad model output."""

    request = f"""
Question:
{question}

Last discussed date:
{last_date}
"""

    response = llm.invoke(
        [
            SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT),
            HumanMessage(content=request),
        ]
    )

    try:
        payload = json.loads(response.content)
        next_step = payload.get("next_step")
    except (json.JSONDecodeError, TypeError, AttributeError):
        return _fallback()

    if next_step not in VALID_ROUTES:
        return _fallback()

    return {
        "next_step": next_step,
        "day_number": parse_int(payload.get("day_number")),
        "offset": parse_int(payload.get("offset")),
        "date": payload.get("date"),
        "parameter": payload.get("parameter"),
        "value": parse_number(payload.get("value")),
        "message": payload.get("message"),
    }