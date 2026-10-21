from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(max_length=4000)

    @field_validator("message")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message is required")
        return value


class ChatResponse(BaseModel):
    reply: str
