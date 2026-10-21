from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.api.deps import get_pipeline
from app.infra.documents_repo import RepositoryError
from app.pipeline.loader import UnsupportedFileType
from app.pipeline.pipeline import IngestionPipeline, InvalidKey
from app.schemas.documents import Document, IngestRequest

router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=Document, status_code=202)
def ingest(body: IngestRequest, background: BackgroundTasks,
           pipeline: IngestionPipeline = Depends(get_pipeline)):
    """Accept a file for ingestion and process it in the background. Poll GET /documents/{doc_id} for progress."""
    try:
        record = pipeline.accept(body.s3_key)
    except (InvalidKey, UnsupportedFileType) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RepositoryError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    background.add_task(pipeline.run, body.s3_key)
    return record
