from fastapi import APIRouter

from app.api.v1 import documents, ingest

api_router = APIRouter()
api_router.include_router(ingest.router)
api_router.include_router(documents.router)
