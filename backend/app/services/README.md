# app/services/

The **business logic** layer: the "what should happen" part of the backend.

Services don't know about HTTP (no requests, status codes or URLs) and don't know which LLM SDK or database is used.
That makes them easy to test (see `tests/test_chat_service.py`) and reuse, e.g. from a background job later.

## Files

| File | Purpose |
|---|---|
| `chat_service.py` | `ChatService.answer(user_id, message, conversation_id)` → `ChatAnswer(reply, conversation_id, sources)` |

## What `answer()` does

```
answer(user_id, message, conversation_id)
  ├── no conversation_id?  → create a new one (UUID), no history
  ├── has conversation_id? → load the last 20 messages from DynamoDB
  │                          another user's conversation → ConversationNotFound (404)
  ├── trim history so it starts with a user message (Claude requires this)
  │
  ├── RAG: find passages
  │     first question → search it as-is
  │     follow-up      → Claude rewrites it into a standalone query ("and for 2 lines?" →
  │                      "Unlimited plan pricing for 2 lines"), or NONE for small talk (no search)
  │     search fails   → continue without passages (logged)
  │
  ├── call Claude with: system rules + earlier turns (plain) + new question wrapped with the passages
  ├── save the plain question and the answer to DynamoDB (passages are not stored)
  │      (if saving fails, the user still gets the answer; the error is logged)
  └── return ChatAnswer(reply, conversation_id, sources)   sources = unique file + page, best first
```

Why only the **new** question carries passages: earlier turns already have their answers, and re-sending old
passages every turn would multiply token costs for no benefit.

## Later additions

- Tenant-specific rules and prompts (pass `tenant_id` to the retriever)
- Store `sources` with each assistant message in DynamoDB, to show them when reloading a conversation
