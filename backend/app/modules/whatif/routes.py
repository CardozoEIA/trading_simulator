# app/modules/whatif/routes.py
import logging

from fastapi import APIRouter, BackgroundTasks, Depends

from app.core.dependencies import get_current_user
from app.modules.insights.service import mark_pending, on_simulation_finished
from app.modules.whatif.schema import WhatIfRequest, WhatIfResponse
from app.modules.whatif.service import run_what_if

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/simulations", tags=["What-if"])


@router.post("/{simulation_id}/what-if", response_model=WhatIfResponse)
def what_if(
    simulation_id: str,
    request: WhatIfRequest,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
):
    result = run_what_if(simulation_id, current_user.id, request.parameter, request.value)

    # same as POST /simulations/start: the finished copy gets its US-26 highlights in the background
    if result["what_if_id"]:
        try:
            mark_pending(result["what_if_id"])
            background_tasks.add_task(on_simulation_finished, result["what_if_id"])
        except Exception:
            logger.exception("Could not schedule insights; the what-if result is unaffected")

    return result
