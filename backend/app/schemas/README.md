# app/schemas/

**Request and response shapes** (the API contract), written with Pydantic.

FastAPI uses these to:
- **validate** incoming JSON automatically (bad input → `422` with a clear error)
- **document** the API at http://localhost:8000/docs
- **shape** the JSON sent back

## Files

| File | Models |
|---|---|
| `chat.py` | `ChatRequest` (`message`: required, trimmed, not blank, max 4000 chars; `conversation_id`: optional, letters/digits/dashes only) and `ChatResponse` (`reply`, `conversation_id`) |

## Schemas vs database models

These describe the JSON that goes **over HTTP**. When a database is added later, its tables go in a separate `app/models/` folder. Keeping them apart means you can change the database without changing the API, or the reverse.
