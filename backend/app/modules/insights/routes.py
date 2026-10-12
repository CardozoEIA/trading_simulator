# app/modules/insights/routes.py
from fastapi import APIRouter, BackgroundTasks, Depends

from app.core.dependencies import get_current_user
from app.modules.insights.schema import SimulationInsightsResponse
from app.modules.insights.service import get_insights, request_generation

router = APIRouter(prefix="/simulations", tags=["Insights"])


@router.get("/{simulation_id}/insights", response_model=SimulationInsightsResponse)
def read_insights(simulation_id: str, background_tasks: BackgroundTasks, current_user=Depends(get_current_user)):
    return get_insights(simulation_id, current_user.id, background_tasks)


@router.post("/{simulation_id}/insights", response_model=SimulationInsightsResponse, status_code=202)
def retry_insights(simulation_id: str, background_tasks: BackgroundTasks, current_user=Depends(get_current_user)):
    return request_generation(simulation_id, current_user.id, background_tasks)
