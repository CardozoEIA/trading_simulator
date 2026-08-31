from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.modules.risk.schema import RiskConfiguration, RiskConfigurationResponse
from app.modules.risk.service import (
    validate_risk_configuration,
    save_risk_configuration
)


router = APIRouter(
    prefix="/risk",
    tags=["Risk"]
)


@router.post(
    "/configuration",
    response_model=RiskConfigurationResponse
)
def configure_risk(
    risk_configuration: RiskConfiguration,
    current_user=Depends(get_current_user)
):
    validate_risk_configuration(risk_configuration, current_user.id)
    return save_risk_configuration(risk_configuration, current_user.id)