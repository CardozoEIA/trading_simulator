# app/modules/decisions/service.py
from fastapi import HTTPException
from app.core.supabase import supabase_admin as supabase
from app.core.validation import is_valid_uuid
from app.services.strategy.schema import Decision

def save_decisions(simulation_id, decisions, executed_dates, prices_by_date) -> None:
    if not decisions:
        return
    rows = [{"simulation_id": simulation_id, "date": d.date.isoformat(),
             "price": prices_by_date[d.date], "action": d.action.value,
             "reason": d.reason, "executed": d.date in executed_dates}
            for d in decisions]
    try:
        supabase.table("simulation_decisions").insert(rows).execute()
    except Exception:
        raise HTTPException(status_code=503, detail="Could not save decisions")

def get_decisions(simulation_id: str, user_id: str) -> list[dict]:
    if not is_valid_uuid(simulation_id):
        raise HTTPException(status_code=404, detail="Simulation not found")
    response = (
        supabase.table("simulation_decisions")
        .select("*, simulations!inner(user_id)")
        .eq("simulation_id", simulation_id)
        .eq("simulations.user_id", user_id)
        .order("date")
        .execute()
    )
    return response.data