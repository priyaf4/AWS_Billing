# app/infra/

Code that talks to **external systems**: databases, storage, queues. Each file wraps one system, so the rest of the app never imports `boto3` directly.

## Files

| File | System | Purpose |
|---|---|---|
| `chat_history.py` | Amazon DynamoDB, table `chat-history` | Save and load chat messages per conversation |

## chat_history.py

`ChatHistoryRepository` has two methods:

| Method | What it does |
|---|---|
| `get_messages(conversation_id, limit)` | Returns the latest `limit` messages, oldest first |
| `add_messages(conversation_id, user_id, messages)` | Saves messages in one batch |

Errors from AWS become one simple `HistoryError`.

### Table layout

One item per message:

| Attribute | Example | Notes |
|---|---|---|
| `PK` | `CONV#5f0c…` | Partition key: all messages of one conversation share it |
| `SK` | `MSG#2026-10-21T10:15:02.123456+00:00#9f3e1a2b` | Sort key: timestamp, so messages come back in order |
| `role` | `user` / `assistant` | |
| `content` | `Why is there a prorated charge…` | |
| `user_id` | `admin` | Owner. Other users get "not found". |
| `tenant_id` | `default` | Ready for multi-tenancy |
| `created_at` | ISO timestamp | |
| `model` | Bedrock model ID | Assistant messages only |

The generic `PK`/`SK` names let other record types live in the same table later (e.g. `USER#alice` / `CONV#…` to list someone's conversations).

**Reading the latest 20** = one `Query` on `PK`, newest first, `Limit=20`, then reversed. It's fast and cheap no matter how long the conversation gets.

### Why `asyncio.to_thread`?

`boto3` is synchronous. Running it in a worker thread keeps the server free to handle other requests while waiting for DynamoDB.

### IAM permissions needed

`dynamodb:Query`, `dynamodb:BatchWriteItem` (plus `GetItem`, `PutItem`, `DescribeTable` for later use) on `arn:aws:dynamodb:<region>:<account>:table/chat-history`.

### Viewing the data

AWS Console → DynamoDB → Tables → `chat-history` → **Explore table items**. Filter on `PK` = `CONV#<id>` to see one conversation.

### Auto-delete (optional, later)

History is currently kept forever. To expire old messages, add an `expires_at` number attribute (Unix seconds) when saving, then turn on **Time to Live** for that attribute in the table's **Additional settings** tab.

## Later additions

| File | Purpose |
|---|---|
| `storage.py` | S3 uploads (moved from the frontend) |
| `vector_store.py` | Embeddings search for RAG |
