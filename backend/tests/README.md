# tests/

Automated tests, run with **pytest**.

```powershell
pytest          # run all tests
pytest -v       # show each test name
```

## Files

| File | What it checks |
|---|---|
| `test_chat.py` | `/health` works; `/api/v1/chat` returns a reply; blank messages are rejected (`422`); an LLM failure becomes `502` |

## How they avoid calling Claude

Each test replaces the real `ChatService` with a `FakeChatService` using FastAPI's dependency override:

```python
app.dependency_overrides[get_chat_service] = lambda: FakeChatService(reply="echo")
```

So tests are fast, free, need no API key, and give the same result on every run, which is what CI/CD needs.

## Adding tests

Create `test_<something>.py` with functions named `test_...`. pytest finds them automatically.
As the project grows, split into `tests/unit/` (services alone) and `tests/integration/` (full API).
