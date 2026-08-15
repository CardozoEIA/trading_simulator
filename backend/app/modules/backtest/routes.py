from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.modules.backtest.schema import (
    BacktestConfiguration,
    BacktestConfigurationResponse
)
from app.modules.backtest.service import (
    get_available_assets,
    validate_configuration
)


router = APIRouter(
    prefix="/backtest",
    tags=["Backtest"]
)


@router.get("/assets")
def get_assets(
    current_user=Depends(get_current_user)
):
    return get_available_assets()


@router.post(
    "/configuration",
    response_model=BacktestConfigurationResponse
)
def configure_backtest(
    configuration: BacktestConfiguration,
    current_user=Depends(get_current_user)
):
    return validate_configuration(
        configuration,
        current_user.id
    )