# app/schemas/

Request and response shapes (Pydantic). FastAPI uses them to validate input, document the API at `/docs`, and shape responses.

| File | Models |
|---|---|
| `documents.py` | `IngestRequest` (`s3_key`), `Document` (one file's status), `DocumentList` |

`Document.status` is one of `pending`, `processing`, `ready`, `failed`.
