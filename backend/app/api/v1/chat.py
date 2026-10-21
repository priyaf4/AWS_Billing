from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_chat_service
from app.genai.llm import LLMError
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, service: ChatService = Depends(get_chat_service)):
    try:
        reply = await service.answer(body.message)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return ChatResponse(reply=reply)
