# app/modules/report/routes.py
from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.modules.report.schema import SimulationReportResponse
from app.modules.report.service import generate_report

router = APIRouter(prefix="/simulations", tags=["Report"])


@router.get("/{simulation_id}/report", response_model=SimulationReportResponse)
def read_report(simulation_id: str, current_user=Depends(get_current_user)):
    return generate_report(simulation_id, current_user.id)
