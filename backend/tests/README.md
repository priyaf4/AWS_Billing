# tests/

Automated tests, run with **pytest**.

```powershell
pytest          # run all tests
pytest -v       # show each test name
```

## Files

| File | What it checks |
|---|---|
| `test_chat.py` | API layer: `/health`; `/api/v1/chat` returns reply + conversation id; missing user → `401`; bad input → `422`; errors map to `502` / `503` / `404` |
| `test_chat_service.py` | Business logic: new conversations get an id; history is sent to the LLM; both messages are saved; other users' conversations are blocked; a failed save still returns the answer. **RAG:** passages reach Claude with their source; history stores the plain question; sources are unique and ranked; follow-ups are rewritten, small talk skips search; search or rewrite failures still produce an answer |

## How they avoid calling Claude and DynamoDB

- **API tests** replace the whole `ChatService` with a `FakeChatService` using FastAPI's dependency override:
  ```python
  app.dependency_overrides[get_chat_service] = lambda: FakeChatService(reply="echo")
  ```
- **Service tests** build a real `ChatService` but give it a `FakeLLM` and an in-memory `FakeHistory`.

So tests are fast, free, need no AWS access, and give the same result on every run, which is what CI/CD needs.

## Adding tests

Create `test_<something>.py` with functions named `test_...`. pytest finds them automatically.
As the project grows, split into `tests/unit/` (services alone) and `tests/integration/` (full API).
