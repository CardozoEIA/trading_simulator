# app/modules/signals/routes.py
from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_user
from app.modules.signals.service import get_signals, get_signal_by_date

router = APIRouter(prefix="/simulations", tags=["Signals"])

@router.get("/{simulation_id}/signals")
def list_signals(simulation_id: str, current_user=Depends(get_current_user)):
    return get_signals(simulation_id, current_user.id)

@router.get("/{simulation_id}/signals/{target_date}")
def get_signal(simulation_id: str, target_date: str, current_user=Depends(get_current_user)):
    return get_signal_by_date(simulation_id, current_user.id, target_date)