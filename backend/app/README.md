# app/

All the backend's Python code lives here. It's one Python package, so imports look like `from app.services.chat_service import ChatService`.

## main.py

The entry point. It:
1. creates the FastAPI application (`app = FastAPI(...)`)
2. plugs in all API routes under the `/api/v1` prefix
3. defines `GET /health`, which servers and Docker use to check the app is alive

`uvicorn app.main:app` loads this file and serves the `app` object.

## Sub-folders, in the order a request travels

| Folder | Role | Analogy |
|---|---|---|
| `api/` | Receives HTTP requests, returns HTTP responses | Reception desk |
| `schemas/` | Defines what a valid request/response looks like | The form you fill in |
| `services/` | Decides what to do with the request | The manager |
| `genai/` | Talks to the LLM, holds prompts | The specialist |
| `core/` | Settings and shared helpers used by everyone | The office rules |

**Rule of thumb:** routes stay thin, logic goes in services, and only `genai/` knows about Claude.

## `__init__.py` files

These empty files tell Python "this folder is a package", so it can be imported. Leave them in place.
