from fastapi import APIRouter, Depends, Response

from app.core.dependencies import get_current_user
from app.modules.custom_strategies import service
from app.modules.custom_strategies.schema import CustomStrategyInput, CustomStrategyResponse, ValidationResponse
from app.services.strategy.custom import parameter_catalog

router = APIRouter(prefix="/custom-strategies", tags=["Custom strategies"])


# Fixed paths go before "/{strategy_id}".
@router.get("/parameters")
def get_parameters(current_user=Depends(get_current_user)):
    """The editable parameters of each base strategy, with defaults and limits (to draw the editor)."""
    return parameter_catalog()


@router.post("/validate", response_model=ValidationResponse)
def validate(strategy: CustomStrategyInput, current_user=Depends(get_current_user)):
    """Checks a configuration without saving it. 422 lists every problem found."""
    return service.validate_strategy(strategy.name, strategy.base_strategy.value, strategy.params)


@router.get("", response_model=list[CustomStrategyResponse])
def list_strategies(current_user=Depends(get_current_user)):
    return service.list_custom_strategies(current_user.id)


@router.post("", response_model=CustomStrategyResponse, status_code=201)
def create(strategy: CustomStrategyInput, current_user=Depends(get_current_user)):
    return service.create_custom_strategy(current_user.id, strategy.name, strategy.base_strategy.value, strategy.params)


@router.get("/{strategy_id}", response_model=CustomStrategyResponse)
def get_one(strategy_id: str, current_user=Depends(get_current_user)):
    return service.get_custom_strategy(strategy_id, current_user.id)


@router.put("/{strategy_id}", response_model=CustomStrategyResponse)
def update(strategy_id: str, strategy: CustomStrategyInput, current_user=Depends(get_current_user)):
    return service.update_custom_strategy(
        strategy_id, current_user.id, strategy.name, strategy.base_strategy.value, strategy.params
    )


@router.delete("/{strategy_id}", status_code=204)
def delete(strategy_id: str, current_user=Depends(get_current_user)):
    service.delete_custom_strategy(strategy_id, current_user.id)
    return Response(status_code=204)
