# app/modules/compare/routes.py
from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.modules.compare.schema import CompareRequest, CompareResponse
from app.modules.compare.service import compare_simulations

router = APIRouter(prefix="/simulations", tags=["Compare"])


@router.post("/compare", response_model=CompareResponse)
def compare(request: CompareRequest, current_user=Depends(get_current_user)):
    return compare_simulations(request.simulation_a, request.simulation_b, current_user.id)
