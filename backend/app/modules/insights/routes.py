# app/modules/insights/routes.py
from fastapi import APIRouter, BackgroundTasks, Depends

from app.core.dependencies import get_current_user
from app.modules.insights.schema import SimulationInsightsResponse
from app.modules.insights.service import generate_insights, get_insights, request_generation

router = APIRouter(prefix="/simulations", tags=["Insights"])


@router.get("/{simulation_id}/insights", response_model=SimulationInsightsResponse)
def read_insights(simulation_id: str, current_user=Depends(get_current_user)):
    return get_insights(simulation_id, current_user.id)


@router.post("/{simulation_id}/insights", response_model=SimulationInsightsResponse, status_code=202)
def regenerate_insights(
    simulation_id: str,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
):
    response = request_generation(simulation_id, current_user.id)
    background_tasks.add_task(generate_insights, simulation_id)
    return response
