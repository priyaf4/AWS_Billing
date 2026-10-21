# app/services/

The **business logic** layer: the "what should happen" part of the backend.

Services don't know about HTTP (no requests, status codes or URLs) and don't know which LLM SDK or database is used.
That makes them easy to test (see `tests/test_chat_service.py`) and reuse, e.g. from a background job later.

## Files

| File | Purpose |
|---|---|
| `chat_service.py` | `ChatService.answer(user_id, message, conversation_id)`: returns `(reply, conversation_id)` |

## What `answer()` does

```
answer(user_id, message, conversation_id)
  ├── no conversation_id?  → create a new one (UUID), no history
  ├── has conversation_id? → load the last 20 messages from DynamoDB
  │                          another user's conversation → ConversationNotFound (404)
  ├── trim history so it starts with a user message (Claude requires this)
  ├── call the LLM with: system prompt + history + new question
  ├── save the question and the answer to DynamoDB
  │      (if saving fails, the user still gets the answer; the error is logged)
  └── return (reply, conversation_id)
```

## Later additions

- Search the PDFs for relevant text before calling the LLM (RAG)
- Tenant-specific rules and prompts
- New services in their own files, e.g. `ingestion_service.py` for loading PDFs
