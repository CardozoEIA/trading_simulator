# app/modules/agent/routes.py
from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_user
from app.modules.agent.schema import ExplainRequest, ExplainResponse
from app.modules.agent.service import explain_decision

router = APIRouter(prefix="/simulations", tags=["Agent"])

@router.post("/{simulation_id}/explain", response_model=ExplainResponse)
def explain(simulation_id: str, request: ExplainRequest, current_user=Depends(get_current_user)):
    explanation = explain_decision(simulation_id, current_user.id, request.date)
    return ExplainResponse(explanation=explanation)