import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_documents, get_pipeline
from app.infra.documents_repo import RepositoryError
from app.main import app
from app.pipeline.loader import UnsupportedFileType
from app.pipeline.pipeline import InvalidKey

RECORD = {
    "doc_id": "abc",
    "file_name": "Rate_Guide.pdf",
    "s3_key": "uploads/1-Rate_Guide.pdf",
    "status": "pending",
    "updated_at": "2026-10-21T10:00:00+00:00",
}


class FakePipeline:
    def __init__(self, error=None):
        self.error = error
        self.ran = []

    def accept(self, s3_key):
        if self.error:
            raise self.error
        return {**RECORD, "s3_key": s3_key}

    def run(self, s3_key):
        self.ran.append(s3_key)


class FakeDocuments:
    def __init__(self, records=None, error=None):
        self.records = records or []
        self.error = error

    def list_all(self):
        if self.error:
            raise self.error
        return self.records

    def get(self, doc_id):
        return next((r for r in self.records if r["doc_id"] == doc_id), None)


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_ingest_accepts_and_runs_in_background(client):
    pipeline = FakePipeline()
    app.dependency_overrides[get_pipeline] = lambda: pipeline

    res = client.post("/api/v1/ingest", json={"s3_key": "uploads/1-Rate_Guide.pdf"})

    assert res.status_code == 202
    assert res.json()["status"] == "pending"
    assert pipeline.ran == ["uploads/1-Rate_Guide.pdf"]  # TestClient runs background tasks after replying


@pytest.mark.parametrize("error", [InvalidKey("bad key"), UnsupportedFileType("bad type")])
def test_ingest_rejects_bad_requests(client, error):
    app.dependency_overrides[get_pipeline] = lambda: FakePipeline(error=error)
    res = client.post("/api/v1/ingest", json={"s3_key": "x"})
    assert res.status_code == 400


def test_list_documents_newest_first(client):
    older = {**RECORD, "doc_id": "old", "updated_at": "2026-10-20T10:00:00+00:00"}
    app.dependency_overrides[get_documents] = lambda: FakeDocuments([older, RECORD])
    ids = [d["doc_id"] for d in client.get("/api/v1/documents").json()["documents"]]
    assert ids == ["abc", "old"]


def test_list_documents_store_down(client):
    app.dependency_overrides[get_documents] = lambda: FakeDocuments(error=RepositoryError("down"))
    assert client.get("/api/v1/documents").status_code == 503


def test_get_document_and_not_found(client):
    app.dependency_overrides[get_documents] = lambda: FakeDocuments([RECORD])
    assert client.get("/api/v1/documents/abc").json()["file_name"] == "Rate_Guide.pdf"
    assert client.get("/api/v1/documents/missing").status_code == 404
