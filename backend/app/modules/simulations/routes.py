from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.modules.simulations.schema import (
    SimulationStartRequest,
    SimulationResponse,
    ConfigurationSummaryResponse
)
from app.modules.simulations.service import (
    start_simulation,
    get_simulation_status,
    get_full_configuration
)


router = APIRouter(
    prefix="/simulations",
    tags=["Simulations"]
)


@router.get(
    "/configuration/{configuration_id}/summary",
    response_model=ConfigurationSummaryResponse
)
def get_configuration_summary(
    configuration_id: str,
    current_user=Depends(get_current_user)
):
    return get_full_configuration(configuration_id, current_user.id)


@router.post("/start", response_model=SimulationResponse)
def start(
    request: SimulationStartRequest,
    current_user=Depends(get_current_user)
):
    return start_simulation(request.configuration_id, current_user.id)


@router.get("/{simulation_id}/status", response_model=SimulationResponse)
def status(
    simulation_id: str,
    current_user=Depends(get_current_user)
):
    return get_simulation_status(simulation_id, current_user.id)