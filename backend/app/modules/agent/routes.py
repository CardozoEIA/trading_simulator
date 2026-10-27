# app/modules/agent/routes.py
from fastapi import APIRouter, Depends
from app.core.dependencies import get_current_user
from app.modules.agent import traces
from app.modules.agent.schema import ExplainRequest, ExplainResponse, TraceRecord
from app.modules.agent.service import explain_decision

router = APIRouter(prefix="/simulations", tags=["Agent"])

@router.post("/{simulation_id}/explain", response_model=ExplainResponse)
def explain(simulation_id: str, request: ExplainRequest, current_user=Depends(get_current_user)):
    return explain_decision(simulation_id, current_user.id, request.date)


@router.get("/{simulation_id}/traces", response_model=list[TraceRecord])
def get_traces(simulation_id: str, date: str | None = None, current_user=Depends(get_current_user)):
    """US-31: what the agent used for its explanations of this simulation (newest first; optionally one date)."""
    return traces.get_traces(simulation_id, current_user.id, date)
