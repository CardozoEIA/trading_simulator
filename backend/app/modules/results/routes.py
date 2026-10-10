from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.modules.results.schema import SimulationResultsSummary, SimulationMetrics
from app.modules.results.service import get_results_summary, get_metrics

router = APIRouter(prefix="/results", tags=["Results"])


@router.get("/{simulation_id}/summary", response_model=SimulationResultsSummary)
def summary(simulation_id: str, current_user=Depends(get_current_user)):
    return get_results_summary(simulation_id, current_user.id)

@router.get("/{simulation_id}/metrics", response_model=SimulationMetrics)
def metrics(simulation_id: str, current_user=Depends(get_current_user)):
    return get_metrics(simulation_id, current_user.id)