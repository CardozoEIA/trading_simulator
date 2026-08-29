from fastapi import HTTPException

from app.core.supabase import supabase
from app.core.validation import is_valid_uuid


def get_full_configuration(configuration_id: str, user_id: str) -> dict:
    """Joins backtest_configurations + risk_configurations for a given configuration.

    This is the point where the pieces saved separately during US-03/US-04/US-06
    come together into a single configuration object. Used both to show the
    confirmation summary (US-05) and to start a simulation (US-07).
    """
    if not is_valid_uuid(configuration_id):
        raise HTTPException(
            status_code=404,
            detail="The referenced simulation configuration was not found"
        )

    try:
        config_response = (
            supabase
            .table("backtest_configurations")
            .select("*")
            .eq("id", configuration_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the database, please try again"
        )

    if not config_response.data:
        raise HTTPException(
            status_code=404,
            detail="The referenced simulation configuration was not found"
        )

    try:
        risk_response = (
            supabase
            .table("risk_configurations")
            .select("*")
            .eq("configuration_id", configuration_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the database, please try again"
        )

    if not risk_response.data:
        raise HTTPException(
            status_code=400,
            detail="Risk parameters must be configured before starting the simulation"
        )

    return {
        **config_response.data[0],
        "risk": risk_response.data[0]
    }


def start_simulation(configuration_id: str, user_id: str) -> dict:
    """Validates the full configuration exists and creates a new simulation run."""
    get_full_configuration(configuration_id, user_id)

    simulation_data = {
        "configuration_id": configuration_id,
        "user_id": user_id,
        "status": "RUNNING"
    }

    try:
        saved = (
            supabase
            .table("simulations")
            .insert(simulation_data)
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the database, please try again"
        )

    if not saved.data:
        raise HTTPException(
            status_code=500,
            detail="Could not start the simulation"
        )

    return saved.data[0]


def get_simulation_status(simulation_id: str, user_id: str) -> dict:
    if not is_valid_uuid(simulation_id):
        raise HTTPException(
            status_code=404,
            detail="Simulation not found"
        )

    try:
        response = (
            supabase
            .table("simulations")
            .select("*")
            .eq("id", simulation_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the database, please try again"
        )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="Simulation not found"
        )

    return response.data[0]