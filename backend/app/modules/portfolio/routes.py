# app/modules/portfolio/routes.py
from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_user
from app.modules.portfolio.service import get_trades

router = APIRouter(prefix="/simulations", tags=["Portfolio"])

@router.get("/{simulation_id}/trades")
def list_trades(simulation_id: str, current_user=Depends(get_current_user)):
    return get_trades(simulation_id, current_user.id)