import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Response

from app.core.dependencies import get_current_user
from app.modules.simulations.schema import (
    SimulationStartRequest,
    SimulationResponse,
    ConfigurationSummaryResponse,
    SimulationHistoryItem
)
from app.modules.simulations.service import (
    start_simulation,
    get_simulation_status,
    build_configuration_summary,
    get_simulation_history,
    delete_simulation,
)
from app.modules.chat.service import forget_conversation
from app.modules.insights.service import mark_pending, on_simulation_finished

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulations", tags=["Simulations"])


@router.get(
    "/configuration/{configuration_id}/summary",
    response_model=ConfigurationSummaryResponse,
)
def get_configuration_summary(
    configuration_id: str, current_user=Depends(get_current_user)
):
    return build_configuration_summary(configuration_id, current_user.id)


@router.post("/start", response_model=SimulationResponse)
def start(
    request: SimulationStartRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user)
):
    simulation = start_simulation(request.configuration_id, current_user.id)

    # US-26: the finished run triggers the insights agent in the background
    if simulation["status"] in ("FINISHED", "STOPPED_BY_RISK"):
        try:
            mark_pending(simulation["id"])
            background_tasks.add_task(on_simulation_finished, simulation["id"])
        except Exception:
            logger.exception("Could not schedule insights; results are unaffected")

    return simulation


@router.get("/{simulation_id}/status", response_model=SimulationResponse)
def status(
    simulation_id: str,
    current_user=Depends(get_current_user)
):
    return get_simulation_status(simulation_id, current_user.id)

@router.get("/history", response_model=list[SimulationHistoryItem])
def history(current_user=Depends(get_current_user)):
    return get_simulation_history(current_user.id)


@router.delete("/{simulation_id}", status_code=204)
def delete(simulation_id: str, current_user=Depends(get_current_user)):
    delete_simulation(simulation_id, current_user.id)
    forget_conversation(simulation_id, current_user.id)
    return Response(status_code=204)
