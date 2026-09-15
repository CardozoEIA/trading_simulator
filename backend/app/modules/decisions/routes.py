# app/modules/decisions/routes.py
from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_user
from app.modules.decisions.service import get_decisions

router = APIRouter(prefix="/simulations", tags=["Decisions"])

@router.get("/{simulation_id}/decisions")
def list_decisions(simulation_id: str, current_user=Depends(get_current_user)):
    return get_decisions(simulation_id, current_user.id)