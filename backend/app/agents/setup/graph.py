# app/agents/setup/graph.py
"""Natural-language setup of a simulation (US-29).

    extract -> validate -> ask_missing -> END    (missing or invalid fields)
                       \\-> propose -----> END    (complete configuration proposal)

The model only extracts what the student wrote; parsing, validation and every message
are code. Nothing is saved: the proposal opens the normal setup flow, where the student
confirms each step.
"""
import json
import logging
from datetime import date
from typing import TypedDict

from fastapi import HTTPException
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from app.agents.common.llm import get_chat_model
from app.agents.setup.parse import FIELD_QUESTIONS, FIELDS, coerce, strategy_label
from app.agents.setup.prompts import SETUP_SYSTEM_PROMPT
from app.modules.backtest.schema import BacktestConfiguration
from app.modules.backtest.service import validate_configuration

logger = logging.getLogger(__name__)

BACKTEST_FIELDS = ("asset", "start_date", "end_date", "initial_capital", "strategies")


class SetupState(TypedDict, total=False):
    description: str
    today: str
    raw: dict                   # model extraction, untrusted
    values: dict                # parsed values, None when missing
    problems: dict              # field -> plain-language message
    missing_fields: list[str]
    status: str                 # "complete" | "incomplete"
    message: str


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def understood(values: dict) -> str:
    """What the agent already understood, in words (only values the student gave)."""
    parts = []
    if values.get("asset"):
        parts.append("the S&P 500")
    if values.get("start_date") and values.get("end_date"):
        parts.append(f"from {values['start_date']} to {values['end_date']}")
    if values.get("initial_capital"):
        parts.append(f"${values['initial_capital']:,.2f} of capital")
    if values.get("strategies"):
        parts.append(_join([strategy_label(s) for s in values["strategies"]]))
    for field, label in (("stop_loss_percentage", "stop-loss"), ("max_position_size", "max position"),
                         ("max_drawdown", "max drawdown")):
        if values.get(field):
            parts.append(f"{label} {values[field]:g}%")
    return ", ".join(parts)


def _validate_backtest(values: dict) -> str | None:
    """Reuses the setup validation (asset, date order, data available). Reads only, never writes."""
    configuration = BacktestConfiguration(
        asset=values["asset"],
        start_date=date.fromisoformat(values["start_date"]),
        end_date=date.fromisoformat(values["end_date"]),
        initial_capital=values["initial_capital"],
        strategies=values["strategies"],
    )
    try:
        validate_configuration(configuration)
    except HTTPException as error:
        if error.status_code >= 500:
            raise
        return error.detail
    return None


def build_setup_graph(llm=None, today: date | None = None):
    llm = llm or get_chat_model(format="json")

    def extract(state: SetupState) -> SetupState:
        request = f"Today is {(today or date.today()).isoformat()}.\n\nDescription:\n{state['description']}"
        response = llm.invoke([SystemMessage(content=SETUP_SYSTEM_PROMPT), HumanMessage(content=request)])
        try:
            raw = json.loads(response.content)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Setup model returned invalid JSON: %s", str(response.content)[:200])
            raw = {}
        return {"raw": raw if isinstance(raw, dict) else {}}

    def validate(state: SetupState) -> SetupState:
        values, problems = coerce(state["raw"], state["description"])

        if values["start_date"] and values["end_date"] and values["start_date"] >= values["end_date"]:
            problems["end_date"] = (
                f"The end date ({values['end_date']}) must be after the start date ({values['start_date']})."
            )
            values["end_date"] = None

        if all(values[f] is not None for f in BACKTEST_FIELDS):
            error = _validate_backtest(values)
            if error:
                problems["start_date"] = f"{error}. Please choose another period."
                values["start_date"] = values["end_date"] = None

        missing = [f for f in FIELDS if values[f] is None]
        return {"values": values, "problems": problems, "missing_fields": missing}

    def ask_missing(state: SetupState) -> SetupState:
        problems = state["problems"]
        lines = []
        known = understood(state["values"])
        if known:
            lines.append(f"So far I understood: {known}.")
        lines.extend(problems[f] for f in FIELDS if f in problems)
        still_needed = [FIELD_QUESTIONS[f] for f in state["missing_fields"] if f not in problems]
        if still_needed:
            lines.append(f"I still need {_join(still_needed)}.")
        lines.append("Could you tell me?")
        return {"status": "incomplete", "message": " ".join(lines)}

    def propose(state: SetupState) -> SetupState:
        return {
            "status": "complete",
            "message": (
                f"Here is the simulation I understood: {understood(state['values'])}. Review it and confirm "
                "to open the setup with these values. Nothing is saved until you confirm each step."
            ),
        }

    def after_validate(state: SetupState) -> str:
        return "ask_missing" if state["missing_fields"] else "propose"

    graph = StateGraph(SetupState)
    graph.add_node("extract", extract)
    graph.add_node("validate", validate)
    graph.add_node("ask_missing", ask_missing)
    graph.add_node("propose", propose)
    graph.add_edge(START, "extract")
    graph.add_edge("extract", "validate")
    graph.add_conditional_edges("validate", after_validate, ["ask_missing", "propose"])
    graph.add_edge("ask_missing", END)
    graph.add_edge("propose", END)
    return graph.compile()
