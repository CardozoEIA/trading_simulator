from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.modules.knowledge import service
from app.modules.knowledge.schema import AskRequest, AskResponse, HistoryResponse

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])


@router.post("/ask", response_model=AskResponse)
def ask_agent(body: AskRequest, current_user=Depends(get_current_user)):
    return service.ask(current_user.id, body.message)


@router.get("/history", response_model=HistoryResponse)
def history(current_user=Depends(get_current_user)):
    return service.get_history(current_user.id)


@router.delete("/history", status_code=204)
def clear_history(current_user=Depends(get_current_user)):
    service.reset_history(current_user.id)
