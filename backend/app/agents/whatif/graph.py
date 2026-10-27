# app/agents/whatif/graph.py
"""What-if re-run of a simulation with one changed risk limit (US-28).

    load -> copy -> run --(finished)--> compare -> END
                       \\-(failed / too slow)-> fallback -> END

Entered only from POST /simulations/{id}/what-if, i.e. after the student confirmed the
plan in the UI. `copy` writes a NEW configuration and risk configuration; the original
rows and the original simulation are never updated. `run` reuses the simulation engine
with a time limit; `compare` reuses the US-27 comparison.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import date
from typing import TypedDict

from fastapi import HTTPException
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from app.agents.chat.support.proposals import build_proposal
from app.agents.common.tracing import child_config
from app.agents.whatif.plan import expected_effect
from app.modules.backtest.schema import BacktestConfiguration
from app.modules.backtest.service import save_configuration, validate_configuration
from app.modules.compare.service import compare_simulations, compare_without_explanation
from app.modules.risk.schema import RiskConfiguration
from app.modules.risk.service import save_risk_configuration, validate_risk_configuration
from app.modules.simulations.service import get_full_configuration, get_simulation_status, start_simulation

logger = logging.getLogger(__name__)

WHAT_IF_TIMEOUT_SECONDS = 90
RISK_FIELDS = ("stop_loss_percentage", "max_position_size", "max_drawdown")


class WhatIfState(TypedDict, total=False):
    user_id: str
    simulation_id: str
    parameter: str
    value: float
    original: dict                  # original configuration + risk (read only)
    proposal: dict                  # {parameter, label, current, suggested, plan}
    configuration_id: str           # the NEW configuration (copy with the changed parameter)
    what_if_id: str | None
    comparison: dict | None
    fallback: str | None            # qualitative explanation when the re-run failed or was too slow
    message: str


def build_what_if_graph(llm=None, runner=None, timeout: float = WHAT_IF_TIMEOUT_SECONDS):
    runner = runner or start_simulation

    def load(state: WhatIfState) -> WhatIfState:
        simulation = get_simulation_status(state["simulation_id"], state["user_id"])  # 404 when not owned
        if simulation["status"] == "RUNNING":
            raise HTTPException(status_code=409, detail="The simulation is still running")
        original = get_full_configuration(simulation["configuration_id"], state["user_id"])

        proposal, error = build_proposal(state["parameter"], state["value"], original["risk"])
        if error:
            raise HTTPException(status_code=400, detail=error)
        return {"original": original, "proposal": proposal}

    def copy(state: WhatIfState) -> WhatIfState:
        original, user_id = state["original"], state["user_id"]
        configuration = BacktestConfiguration(
            asset=original["asset"],
            start_date=date.fromisoformat(str(original["start_date"])),
            end_date=date.fromisoformat(str(original["end_date"])),
            initial_capital=original["initial_capital"],
            # custom strategies (US-21) travel as snapshots, not as codes
            strategies=[s for s in original["strategies"] if not s.startswith("CUSTOM:")],
            custom_strategy_ids=[c["id"] for c in original.get("custom_strategies") or []],
            ensemble_threshold=original.get("ensemble_threshold"),
        )
        records = validate_configuration(configuration)
        extra = {"custom_snapshots": original["custom_strategies"]} if original.get("custom_strategies") else {}
        saved = save_configuration(configuration, user_id, records, **extra)

        risk_values = {field: float(original["risk"][field]) for field in RISK_FIELDS}
        risk_values[state["proposal"]["parameter"]] = state["proposal"]["suggested"]
        risk = RiskConfiguration(configuration_id=saved["id"], **risk_values)
        validate_risk_configuration(risk, user_id)
        save_risk_configuration(risk, user_id)
        return {"configuration_id": saved["id"]}

    def run(state: WhatIfState) -> WhatIfState:
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(runner, state["configuration_id"], state["user_id"])
        executor.shutdown(wait=False)  # a run that is too slow keeps going in the background
        try:
            simulation = future.result(timeout=timeout)
            return {"what_if_id": simulation["id"]}
        except FutureTimeout:
            logger.warning("What-if run of %s took longer than %ss", state["simulation_id"], timeout)
            return {"what_if_id": None, "message": (
                "The new simulation is taking too long, so here is the expected effect instead. "
                "When it finishes you will find it in your history."
            )}
        except Exception:
            logger.exception("What-if run of %s failed", state["simulation_id"])
            return {"what_if_id": None, "message": (
                "The new simulation could not be run, so here is the expected effect instead."
            )}

    def compare(state: WhatIfState, config: RunnableConfig) -> WhatIfState:
        original_id, what_if_id, user_id = state["simulation_id"], state["what_if_id"], state["user_id"]
        try:
            comparison = compare_simulations(original_id, what_if_id, user_id, llm=llm, config=child_config(config))
            message = "The what-if finished. Here is how it compares with the original run."
        except Exception:
            # the agent could not explain it (e.g. Ollama down): the computed comparison is still useful
            logger.exception("What-if comparison explanation failed")
            comparison = compare_without_explanation(original_id, what_if_id, user_id)
            message = "The what-if finished. The agent could not explain the comparison, but the figures are below."
        return {"comparison": comparison, "message": message}

    def fallback(state: WhatIfState) -> WhatIfState:
        p = state["proposal"]
        return {"comparison": None, "fallback": expected_effect(p["parameter"], p["current"], p["suggested"])}

    def after_run(state: WhatIfState) -> str:
        return "compare" if state.get("what_if_id") else "fallback"

    graph = StateGraph(WhatIfState)
    graph.add_node("load", load)
    graph.add_node("copy", copy)
    graph.add_node("run", run)
    graph.add_node("compare", compare)
    graph.add_node("fallback", fallback)
    graph.add_edge(START, "load")
    graph.add_edge("load", "copy")
    graph.add_edge("copy", "run")
    graph.add_conditional_edges("run", after_run, ["compare", "fallback"])
    graph.add_edge("compare", END)
    graph.add_edge("fallback", END)
    return graph.compile()
