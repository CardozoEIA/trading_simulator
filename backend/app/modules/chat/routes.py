from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse

from app.core.dependencies import get_current_user

from app.modules.chat.schema import (
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
)

from app.modules.chat.service import (
    chat,
    chat_stream,
    get_history,
    reset_conversation,
)


router = APIRouter(
    prefix="/simulations",
    tags=["Chat"],
)


@router.post(
    "/{simulation_id}/chat",
    response_model=ChatResponse,
)
def conversation(
    simulation_id: str,
    body: ChatRequest,
    current_user=Depends(get_current_user),
):
    return chat(
        simulation_id=simulation_id,
        user_id=current_user.id,
        message=body.message,
    )


@router.post("/{simulation_id}/chat/stream")
def conversation_stream(
    simulation_id: str,
    body: ChatRequest,
    current_user=Depends(get_current_user),
):
    return StreamingResponse(
        chat_stream(
            simulation_id=simulation_id,
            user_id=current_user.id,
            message=body.message,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/{simulation_id}/chat/history",
    response_model=ChatHistoryResponse,
)
def conversation_history(
    simulation_id: str,
    current_user=Depends(get_current_user),
):
    return get_history(simulation_id, current_user.id)


@router.delete("/{simulation_id}/chat", status_code=204)
def clear_conversation(
    simulation_id: str,
    current_user=Depends(get_current_user),
):
    reset_conversation(simulation_id, current_user.id)
    return Response(status_code=204)