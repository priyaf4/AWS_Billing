from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_documents
from app.infra.documents_repo import DocumentsRepository, RepositoryError
from app.schemas.documents import Document, DocumentList

router = APIRouter(tags=["documents"])


@router.get("/documents", response_model=DocumentList)
def list_documents(documents: DocumentsRepository = Depends(get_documents)):
    """Every file the ingestor has seen, newest first."""
    try:
        records = documents.list_all()
    except RepositoryError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return DocumentList(documents=sorted(records, key=lambda r: r["updated_at"], reverse=True))


@router.get("/documents/{doc_id}", response_model=Document)
def get_document(doc_id: str, documents: DocumentsRepository = Depends(get_documents)):
    try:
        record = documents.get(doc_id)
    except RepositoryError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    if not record:
        raise HTTPException(status_code=404, detail="Document not found")
    return record
