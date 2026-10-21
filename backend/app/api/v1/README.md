# app/api/v1/

Version 1 of the API. Every route here is served under `/api/v1`.

## Files

| File | Endpoint | What it does |
|---|---|---|
| `router.py` | n/a | Collects all v1 routers into one `api_router`, which `main.py` mounts at `/api/v1` |
| `chat.py` | `POST /api/v1/chat` | Takes `{"message": "..."}`, asks `ChatService` for an answer, returns `{"reply": "..."}` |

## Example

Request:
```json
POST /api/v1/chat
{ "message": "Why is my bill higher this month?" }
```

Response:
```json
{ "reply": "Bills can go up because of ..." }
```

Errors:
| Status | When |
|---|---|
| `422` | Message missing, blank, or longer than 4000 characters |
| `502` | Claude could not answer (bad key, rate limit, network). `detail` explains why. |

## Adding a new endpoint

1. Create `app/api/v1/<name>.py` with `router = APIRouter(tags=["<name>"])` and your routes.
2. Register it in `router.py`: `api_router.include_router(<name>.router)`.
3. Put request/response models in `app/schemas/` and logic in `app/services/`.
