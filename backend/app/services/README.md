# app/services/

The **business logic** layer: the "what should happen" part of the backend.

Services don't know about HTTP (no requests, status codes or URLs) and don't know which LLM SDK is used.
That makes them easy to test and reuse, e.g. from a background job later.

## Files

| File | Purpose |
|---|---|
| `chat_service.py` | `ChatService.answer(message)`: loads the system prompt and asks the LLM for a reply |

## Today vs later

Today `answer()` does one thing: prompt + message → LLM → reply.

This is where the chat gets smarter over time, without touching routes or the LLM wrapper:

```
answer(message)
  ├── (later) load the conversation history
  ├── (later) search the PDFs for relevant text  (RAG)
  ├── (later) apply tenant-specific rules/prompts
  ├── call the LLM
  └── (later) save the reply to history
```

New features get their own service file, e.g. `ingestion_service.py` for loading PDFs.
