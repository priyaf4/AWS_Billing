# app/api/

The **HTTP layer**. Code here only deals with web concerns:
- which URL and method (`POST /chat`)
- reading and validating the request body
- turning errors into HTTP status codes (e.g. LLM failure → `502`)

Code here should **not** contain business logic or call Claude directly. It hands the work to a service.

## Files

| File | Purpose |
|---|---|
| `deps.py` | **Dependencies**: small functions FastAPI calls to give a route what it needs. Today `get_chat_service()` builds the `ChatService` (with one shared Claude client). |
| `v1/` | Version 1 of the API. See `v1/README.md`. |

## Why `deps.py`?

Routes ask for what they need instead of creating it themselves:

```python
async def chat(body: ChatRequest, service: ChatService = Depends(get_chat_service)):
```

Benefits:
- **Tests** can swap in a fake service (`app.dependency_overrides`) so no real API call is made.
- **Later**, `get_current_user()` and `get_tenant()` go here too, and any route can require them with one line.

## Why `v1/`?

If you ever need to change the API in a breaking way, you add `v2/` alongside it. Old clients keep working on `/api/v1/...`.
