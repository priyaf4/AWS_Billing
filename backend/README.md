# GenAI Backend

A Python (FastAPI) service that receives a chat message, sends it to Claude, and returns Claude's answer.
The frontend never talks to Claude directly. It only calls this backend.

## Big picture

```
Browser (chat page)
   │  POST /api/chat
   ▼
Frontend (Next.js)          checks the user is logged in, then forwards the message
   │  POST http://localhost:8000/api/v1/chat
   ▼
Backend (this folder)
   api/v1/chat.py           1. receives the HTTP request, validates it
   services/chat_service.py 2. decides what to do (pick prompt, later: search documents)
   genai/llm.py             3. calls the Claude API
   │
   ▼
Claude API  ──► answer travels back up the same path ──► shown in chat
```

Each layer only calls the layer below it. That keeps every file small and easy to change:
- Change the LLM provider → edit only `genai/llm.py`
- Change the assistant's behaviour → edit only `genai/prompts/billing_assistant.md`
- Add a new endpoint → add a file in `api/v1/`

## Folder map

```
backend/
├── app/                    the application code          → app/README.md
│   ├── main.py             starts the app, registers routes
│   ├── api/                HTTP layer (routes)           → app/api/README.md
│   │   └── v1/             version 1 of the API          → app/api/v1/README.md
│   ├── services/           business logic                → app/services/README.md
│   ├── genai/              everything AI / LLM           → app/genai/README.md
│   │   └── prompts/        prompt text files             → app/genai/prompts/README.md
│   ├── schemas/            request/response shapes       → app/schemas/README.md
│   └── core/               settings and shared basics    → app/core/README.md
├── tests/                  automated tests               → tests/README.md
├── pyproject.toml          project info + dependencies
├── .env.example            template for your secrets/settings
└── .env                    your real settings (never commit this)
```

## Run locally

```powershell
cd backend
python -m venv .venv                 # one time: create a virtual environment
.venv\Scripts\activate               # every new terminal (macOS/Linux: source .venv/bin/activate)
pip install -e ".[dev]"              # install dependencies from pyproject.toml
copy .env.example .env               # one time: then put your AWS keys in .env

uvicorn app.main:app --reload --port 8000
```

- `app.main:app` means "in file `app/main.py`, use the variable `app`".
- `--reload` restarts the server whenever you save a file (for development only).

Once running:
- Interactive API docs: http://localhost:8000/docs (you can send test messages from here)
- Health check: http://localhost:8000/health

Then start the frontend (`cd frontend && npm run dev`) and use the chat page.

## Tests

```powershell
pytest
```

Tests use a fake chat service, so they never call Claude and cost nothing.

## Settings (`.env`)

| Variable | Meaning |
|---|---|
| `LLM_PROVIDER` | `bedrock` (Claude via AWS, uses AWS keys) or `anthropic` (Claude API, uses Anthropic key) |
| `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | AWS credentials for Bedrock. The IAM user needs `bedrock:InvokeModel`. |
| `ANTHROPIC_API_KEY` | Only needed when `LLM_PROVIDER=anthropic` |
| `CLAUDE_MODEL` | Which Claude model to use. Bedrock: `global.anthropic.claude-haiku-4-5-20251001-v1:0` |
| `CLAUDE_EFFORT` | `low` … `max`: how hard Claude thinks. Leave empty for Haiku 4.5, which doesn't support it. |
| `CLAUDE_MAX_TOKENS` | Maximum length of one answer. If it's too low, long answers get cut off. |

## Adding dependencies

Add the package to `dependencies` in `pyproject.toml`, then run `pip install -e ".[dev]"` again.
Test-only tools go under `[project.optional-dependencies] dev`.

## What comes next (and where it goes)

| Feature | Where |
|---|---|
| Answer from the PDFs (RAG) | `genai/` (embeddings, retriever) + `services/chat_service.py` |
| Chat history | `services/chat_service.py` + a database in a new `infra/` folder |
| Authentication | `core/security.py` + `api/deps.py` |
| Multi-tenancy | `api/deps.py` (find tenant) + pass tenant through services |
| Docker | `backend/Dockerfile` |
| CI/CD | `.github/workflows/` at repo root, runs `pytest` |
