from typing import Literal

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    s3_key: str = Field(min_length=1, max_length=1024, examples=["uploads/1792504918425-Rate_Guide.pdf"])


class Document(BaseModel):
    doc_id: str
    file_name: str
    s3_key: str
    status: Literal["pending", "processing", "ready", "failed"]
    updated_at: str
    chunk_count: int | None = None
    page_count: int | None = None
    error: str | None = None


class DocumentList(BaseModel):
    documents: list[Document]
