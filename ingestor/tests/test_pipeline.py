import pytest

from app.core.config import Settings
from app.infra.s3 import FileTooLarge
from app.pipeline.loader import UnsupportedFileType
from app.pipeline.pipeline import (
    IngestionPipeline,
    InvalidKey,
    document_id,
    file_name_from_key,
)

SETTINGS = Settings(
    s3_bucket_name="bucket",
    opensearch_endpoint="https://example.com",
    chunk_size=200,
    chunk_overlap=20,
    _env_file=None,
)


class FakeFiles:
    def __init__(self, files=None, error=None):
        self.files = files or {}
        self.error = error

    def read(self, key):
        if self.error:
            raise self.error
        return self.files[key]


class FakeEmbedder:
    def embed_many(self, texts):
        return [[0.1, 0.2] for _ in texts]


class FakeVectors:
    def __init__(self):
        self.written = {}

    def ensure_index(self):
        pass

    def replace_document_chunks(self, doc_id, chunks):
        self.written[doc_id] = chunks


class FakeDocuments:
    def __init__(self):
        self.history = []  # every save, in order

    def save(self, record):
        self.history.append(record)

    def statuses(self):
        return [r["status"] for r in self.history]


def make(files=None, error=None):
    vectors, documents = FakeVectors(), FakeDocuments()
    pipeline = IngestionPipeline(SETTINGS, FakeFiles(files, error), FakeEmbedder(), vectors, documents)
    return pipeline, vectors, documents


KEY = "uploads/1792504918425-Rate_Guide.txt"


def test_file_name_and_id_ignore_upload_timestamp():
    assert file_name_from_key(KEY, "uploads/") == "Rate_Guide.txt"
    # Re-uploading the same file gets the same id, so its chunks are replaced
    assert document_id("Rate_Guide.txt") == document_id(
        file_name_from_key("uploads/1800000000000-Rate_Guide.txt", "uploads/")
    )


def test_accept_records_pending():
    pipeline, _, documents = make()
    record = pipeline.accept(KEY)
    assert record["status"] == "pending"
    assert documents.statuses() == ["pending"]


@pytest.mark.parametrize("key", ["other/file.txt", "uploads/", "uploads/../secret.txt"])
def test_accept_rejects_keys_outside_uploads(key):
    pipeline, _, _ = make()
    with pytest.raises(InvalidKey):
        pipeline.accept(key)


def test_accept_rejects_unsupported_type():
    pipeline, _, _ = make()
    with pytest.raises(UnsupportedFileType):
        pipeline.accept("uploads/123-photo.jpg")


def test_run_indexes_chunks_and_marks_ready():
    text = ("Prorated charges apply when service starts mid-cycle. " * 20).encode()
    pipeline, vectors, documents = make({KEY: text})

    pipeline.run(KEY)

    assert documents.statuses() == ["processing", "ready"]
    doc_id = document_id("Rate_Guide.txt")
    chunks = vectors.written[doc_id]
    assert len(chunks) == documents.history[-1]["chunk_count"] > 1
    first = chunks[0]
    assert first["doc_id"] == doc_id and first["page"] == 1 and first["chunk_index"] == 0
    assert first["file_name"] == "Rate_Guide.txt" and first["s3_key"] == KEY
    assert first["embedding"] == [0.1, 0.2] and first["text"]


def test_run_marks_empty_file_failed():
    pipeline, vectors, documents = make({KEY: b"   "})
    pipeline.run(KEY)
    assert documents.statuses() == ["processing", "failed"]
    assert "No text found" in documents.history[-1]["error"]
    assert vectors.written == {}


def test_run_shows_known_errors_to_user():
    pipeline, _, documents = make(error=FileTooLarge("File is larger than 20 MB"))
    pipeline.run(KEY)
    assert documents.history[-1]["error"] == "File is larger than 20 MB"


def test_run_hides_unexpected_error_details():
    pipeline, _, documents = make(error=KeyError("internal detail"))
    pipeline.run(KEY)
    assert documents.history[-1]["status"] == "failed"
    assert "internal detail" not in documents.history[-1]["error"]
