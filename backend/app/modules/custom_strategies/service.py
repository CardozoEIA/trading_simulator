# app/modules/custom_strategies/service.py
"""US-21: create, edit, list and delete the student's custom strategies."""
from datetime import datetime, timezone

from fastapi import HTTPException

from app.core.supabase import supabase_admin as supabase
from app.core.validation import is_valid_uuid
from app.services.strategy import custom
from app.services.strategy.custom import InvalidStrategy

DB_ERROR = "Could not connect to the database, please try again"


def _check(name, base_strategy: str, params: dict | None) -> tuple[str, dict]:
    """Validates a strategy; every problem is reported at once with a 422."""
    problems = []
    clean_name = None
    try:
        clean_name = custom.validate_name(name)
    except InvalidStrategy as error:
        problems.extend(error.problems)
    values = None
    try:
        values = custom.validate_parameters(base_strategy, params)
    except InvalidStrategy as error:
        problems.extend(error.problems)
    if problems:
        raise HTTPException(status_code=422, detail=problems)
    return clean_name, values


def validate_strategy(name: str, base_strategy: str, params: dict | None) -> dict:
    clean_name, values = _check(name, base_strategy, params)
    return {"name": clean_name, "base_strategy": base_strategy, "params": values}


def _run(query):
    try:
        return query.execute()
    except Exception:
        raise HTTPException(status_code=503, detail=DB_ERROR)


def _name_taken(user_id: str, name: str, except_id: str | None = None) -> bool:
    rows = _run(supabase.table("custom_strategies").select("id").eq("user_id", user_id).eq("name", name)).data
    return any(row["id"] != except_id for row in rows)


def list_custom_strategies(user_id: str) -> list[dict]:
    return _run(
        supabase.table("custom_strategies").select("*").eq("user_id", user_id).order("created_at", desc=True)
    ).data


def get_custom_strategy(strategy_id: str, user_id: str) -> dict:
    if not is_valid_uuid(strategy_id):
        raise HTTPException(status_code=404, detail="Custom strategy not found")
    rows = _run(
        supabase.table("custom_strategies").select("*").eq("id", strategy_id).eq("user_id", user_id).limit(1)
    ).data
    if not rows:
        raise HTTPException(status_code=404, detail="Custom strategy not found")
    return rows[0]


def create_custom_strategy(user_id: str, name: str, base_strategy: str, params: dict | None) -> dict:
    clean_name, values = _check(name, base_strategy, params)
    if len(list_custom_strategies(user_id)) >= custom.MAX_CUSTOM_STRATEGIES:
        raise HTTPException(status_code=409, detail=f"You can keep up to {custom.MAX_CUSTOM_STRATEGIES} custom strategies")
    if _name_taken(user_id, clean_name):
        raise HTTPException(status_code=409, detail="You already have a custom strategy with that name")
    saved = _run(
        supabase.table("custom_strategies").insert(
            {"user_id": user_id, "name": clean_name, "base_strategy": base_strategy, "params": values}
        )
    ).data
    if not saved:
        raise HTTPException(status_code=500, detail="Could not save the custom strategy")
    return saved[0]


def update_custom_strategy(strategy_id: str, user_id: str, name: str, base_strategy: str, params: dict | None) -> dict:
    get_custom_strategy(strategy_id, user_id)  # 404 when missing or not owned
    clean_name, values = _check(name, base_strategy, params)
    if _name_taken(user_id, clean_name, except_id=strategy_id):
        raise HTTPException(status_code=409, detail="You already have a custom strategy with that name")
    saved = _run(
        supabase.table("custom_strategies")
        .update({
            "name": clean_name, "base_strategy": base_strategy, "params": values,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", strategy_id).eq("user_id", user_id)
    ).data
    if not saved:
        raise HTTPException(status_code=500, detail="Could not save the custom strategy")
    return saved[0]


def delete_custom_strategy(strategy_id: str, user_id: str) -> None:
    get_custom_strategy(strategy_id, user_id)
    _run(supabase.table("custom_strategies").delete().eq("id", strategy_id).eq("user_id", user_id))


def resolve_for_configuration(strategy_ids: list[str], user_id: str) -> list[dict]:
    """Snapshots ({id, name, base_strategy, params}) of the chosen custom strategies, in the order given.
    Raises 404 when one does not exist or belongs to someone else."""
    snapshots, seen = [], set()
    for strategy_id in strategy_ids:
        if strategy_id in seen:
            continue
        seen.add(strategy_id)
        row = get_custom_strategy(strategy_id, user_id)
        snapshots.append({
            "id": row["id"], "name": row["name"], "base_strategy": row["base_strategy"], "params": row["params"],
        })
    return snapshots
