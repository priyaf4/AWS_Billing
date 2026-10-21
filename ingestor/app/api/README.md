# app/api/

The **HTTP layer**: URLs, validation, status codes. No pipeline logic here.

| File | Purpose |
|---|---|
| `deps.py` | Builds the shared objects once (AWS session, `IngestionPipeline`, `DocumentsRepository`) and hands them to routes via `Depends(...)` |
| `v1/` | Version 1 of the API. See `v1/README.md`. |

Tests swap these dependencies for fakes with `app.dependency_overrides`, so no AWS calls are made.
