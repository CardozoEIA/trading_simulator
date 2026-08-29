from fastapi import HTTPException

from app.core.supabase import supabase
from app.core.validation import is_valid_uuid
from app.modules.risk.schema import RiskConfiguration


MIN_PERCENTAGE = 0
MAX_PERCENTAGE = 100


def _validate_percentage(value: float, field_name: str):
    if value <= MIN_PERCENTAGE or value > MAX_PERCENTAGE:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be greater than 0 and at most 100"
        )


def _validate_configuration_ownership(configuration_id: str, user_id: str):
    if not is_valid_uuid(configuration_id):
        raise HTTPException(
            status_code=404,
            detail="The referenced simulation configuration was not found"
        )

    try:
        response = (
            supabase
            .table("backtest_configurations")
            .select("id")
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

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail="The referenced simulation configuration was not found"
        )


def validate_risk_configuration(risk_configuration: RiskConfiguration, user_id: str):
    """Validates ranges and that the configuration belongs to the current user."""
    _validate_configuration_ownership(risk_configuration.configuration_id, user_id)
    _validate_percentage(risk_configuration.stop_loss_percentage, "Stop-loss")
    _validate_percentage(risk_configuration.max_position_size, "Max position size")
    _validate_percentage(risk_configuration.max_drawdown, "Max drawdown")


def save_risk_configuration(risk_configuration: RiskConfiguration, user_id: str) -> dict:
    """Persists an already-validated risk configuration."""
    risk_data = {
        "configuration_id": risk_configuration.configuration_id,
        "user_id": user_id,
        "stop_loss_percentage": risk_configuration.stop_loss_percentage,
        "max_position_size": risk_configuration.max_position_size,
        "max_drawdown": risk_configuration.max_drawdown
    }

    try:
        saved = (
            supabase
            .table("risk_configurations")
            .insert(risk_data)
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
            detail="Could not save the risk configuration"
        )

    return saved.data[0]