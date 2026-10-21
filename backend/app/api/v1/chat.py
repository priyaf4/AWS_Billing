from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_chat_service, get_user_id
from app.genai.llm import LLMError
from app.infra.chat_history import HistoryError
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService, ConversationNotFound

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user_id: str = Depends(get_user_id),
    service: ChatService = Depends(get_chat_service),
):
    try:
        reply, conversation_id = await service.answer(user_id, body.message, body.conversation_id)
    except ConversationNotFound as e:
        raise HTTPException(status_code=404, detail="Conversation not found") from e
    except HistoryError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return ChatResponse(reply=reply, conversation_id=conversation_id)
