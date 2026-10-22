# GenAI Backend

A Python (FastAPI) service that receives a chat message, finds the relevant parts of the company's documents (RAG),
and has Claude answer from them. The frontend never talks to Claude directly. It only calls this backend.

The documents are indexed by the separate **ingestor** service (`../ingestor`); this backend only searches them.

## Big picture

```
Browser (chat page)
   │  POST /api/chat
   ▼
Frontend (Next.js)          checks the user is logged in, then forwards the message
   │  POST http://localhost:8001/api/v1/chat   (BACKEND_URL)
   ▼
Backend (this folder)
   api/v1/chat.py           1. receives the HTTP request, validates it
   services/chat_service.py 2. runs the steps below
   infra/chat_history.py    3. loads the last 20 messages from DynamoDB
   genai/llm.py             4. follow-up? Claude rewrites it into a standalone search query ("NONE" for small talk)
   genai/retriever.py       5. embeds the query (Titan) → searches OpenSearch "kb-chunks" → keeps passages scoring ≥ 1.15
   genai/llm.py             6. calls Claude with: system rules + history + passages + question
   infra/chat_history.py    7. saves the plain question and the answer to DynamoDB
   │
   ▼
answer + conversation_id + sources travel back up ──► shown in chat, with "Sources: FAQs (p. 2) · ..."
```

The frontend keeps the `conversation_id` and sends it with the next question, so Claude remembers the conversation. Refreshing the page starts a new conversation.

If the knowledge base can't be searched, the chat still answers. The prompt then tells Claude not to state company prices or rules.

Each layer only calls the layer below it. That keeps every file small and easy to change:
- Change the LLM provider → edit only `genai/llm.py`
- Change the assistant's behaviour → edit only `genai/prompts.py` (all prompts live there)
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
│   │   └── prompts.py      ALL prompts, in one file
│   ├── infra/              databases & AWS services      → app/infra/README.md
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

Tests use fakes (LLM, history, retriever), so they never call AWS and cost nothing.

## Settings (`.env`)

| Variable | Meaning |
|---|---|
| `LLM_PROVIDER` | `bedrock` (Claude via AWS, uses AWS keys) or `anthropic` (Claude API, uses Anthropic key) |
| `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | AWS credentials for Bedrock. The IAM user needs `bedrock:InvokeModel`. |
| `ANTHROPIC_API_KEY` | Only needed when `LLM_PROVIDER=anthropic` |
| `CLAUDE_MODEL` | Which Claude model to use. Bedrock: `global.anthropic.claude-haiku-4-5-20251001-v1:0` |
| `CLAUDE_EFFORT` | `low` … `max`: how hard Claude thinks. Leave empty for Haiku 4.5, which doesn't support it. |
| `CLAUDE_MAX_TOKENS` | Maximum length of one answer. If it's too low, long answers get cut off. |
| `CHAT_TABLE_NAME` | DynamoDB table for chat history (default `chat-history`). The IAM user needs `dynamodb:Query` and `dynamodb:BatchWriteItem` on it. |
| `CHAT_HISTORY_LIMIT` | How many earlier messages are sent to Claude with each question (default `20`) |
| `OPENSEARCH_ENDPOINT`, `OPENSEARCH_INDEX` | Knowledge base to search (index `kb-chunks`). Leave the endpoint empty to answer without documents. |
| `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS` | `amazon.titan-embed-text-v2:0`, `1024`. **Must match the ingestor.** The IAM user needs `bedrock:InvokeModel` on this model. |
| `RAG_TOP_K` | Passages given to Claude per question (default `5`) |
| `RAG_MIN_SCORE` | Relevance cutoff (default `1.15`; score = 1 + cosine similarity). Measured: on-topic 1.27–1.76, off-topic ≤ 1.09. |

## Adding dependencies

Add the package to `dependencies` in `pyproject.toml`, then run `pip install -e ".[dev]"` again.
Test-only tools go under `[project.optional-dependencies] dev`.

## What comes next (and where it goes)

| Feature | Where |
|---|---|
| Authentication | `core/security.py` + `api/deps.py` |
| Multi-tenancy | `api/deps.py` (find tenant) + pass tenant through services |
| Docker | `backend/Dockerfile` |
| CI/CD | `.github/workflows/` at repo root, runs `pytest` |
