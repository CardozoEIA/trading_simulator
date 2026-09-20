# app/modules/signals/service.py
from fastapi import HTTPException
from app.core.supabase import supabase_admin as supabase
from app.core.validation import is_valid_uuid
from app.services.indicators.calculator import IndicatorSnapshot


def save_signals(simulation_id: str, snapshots: list[IndicatorSnapshot]) -> None:
    if not snapshots:
        return
    rows = [{
        "simulation_id": simulation_id, "date": s.date.isoformat(), "price": s.price,
        "sma_short": s.sma_short, "sma_long": s.sma_long, "rsi": s.rsi,
        "bollinger_mean": s.bollinger_mean, "bollinger_upper": s.bollinger_upper,
        "bollinger_lower": s.bollinger_lower, "momentum": s.momentum
    } for s in snapshots]
    try:
        supabase.table("simulation_signals").insert(rows).execute()
    except Exception:
        raise HTTPException(status_code=503, detail="Could not save technical signals")


def get_signals(simulation_id: str, user_id: str) -> list[dict]:
    response = (
        supabase.table("simulation_signals")
        .select("*, simulations!inner(user_id)")
        .eq("simulation_id", simulation_id)
        .eq("simulations.user_id", user_id)
        .order("date")
        .execute()
    )
    return response.data


def get_signal_by_date(simulation_id: str, user_id: str, target_date: str) -> dict:
    if not is_valid_uuid(simulation_id):
        raise HTTPException(status_code=404, detail="Simulation not found")
    response = (
        supabase.table("simulation_signals")
        .select("*, simulations!inner(user_id)")
        .eq("simulation_id", simulation_id)
        .eq("simulations.user_id", user_id)
        .eq("date", target_date)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise HTTPException(status_code=404, detail="No signal found for that date")
    return response.data[0]