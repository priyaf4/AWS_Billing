from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(max_length=4000)
    # Omit to start a new conversation; send back the id from the previous reply to continue it
    conversation_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9-]+$")

    @field_validator("message")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message is required")
        return value


class Source(BaseModel):
    file_name: str
    page: int


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    # Documents the answer was based on (empty when nothing relevant was found)
    sources: list[Source] = []
