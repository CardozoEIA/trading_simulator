# app/modules/setup/routes.py
from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.modules.setup.schema import SetupParseRequest, SetupParseResponse
from app.modules.setup.service import parse_setup

router = APIRouter(prefix="/simulations", tags=["Setup"])


@router.post("/setup/parse", response_model=SetupParseResponse)
def parse(request: SetupParseRequest, current_user=Depends(get_current_user)):
    return parse_setup(request.description)
