# app/api/v1/

Version 1 of the API. Every route here is served under `/api/v1`.

## Files

| File | Endpoint | What it does |
|---|---|---|
| `router.py` | n/a | Collects all v1 routers into one `api_router`, which `main.py` mounts at `/api/v1` |
| `chat.py` | `POST /api/v1/chat` | Takes a message (and optional conversation id), asks `ChatService` for an answer, returns the reply and conversation id |

## Example

First question (no `conversation_id` → new conversation):
```http
POST /api/v1/chat
X-User-Id: admin

{ "message": "Why is my bill higher this month?" }
```
```json
{ "reply": "Bills can go up because of ...", "conversation_id": "5f0c2e8a-..." }
```

Follow-up (send the id back so Claude sees the earlier messages):
```json
{ "message": "And how do I avoid that next month?", "conversation_id": "5f0c2e8a-..." }
```

`X-User-Id` is set by the frontend after it checks the login session. Testing from `/docs`: fill in the `x-user-id` field.

Errors:
| Status | When |
|---|---|
| `401` | `X-User-Id` header missing |
| `404` | `conversation_id` belongs to another user |
| `422` | Message missing, blank, or longer than 4000 characters; or invalid `conversation_id` |
| `502` | Claude could not answer (bad key, rate limit, network). `detail` explains why. |
| `503` | Chat history (DynamoDB) could not be loaded |

## Adding a new endpoint

1. Create `app/api/v1/<name>.py` with `router = APIRouter(tags=["<name>"])` and your routes.
2. Register it in `router.py`: `api_router.include_router(<name>.router)`.
3. Put request/response models in `app/schemas/` and logic in `app/services/`.
