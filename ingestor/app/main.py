import logging

from fastapi import FastAPI

from app.api.v1.router import api_router

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="RAG Ingestor")
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
