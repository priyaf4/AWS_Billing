# app/genai/

Everything specific to **AI / LLMs** lives here, so it's all in one place.

## Files

| File / folder | Purpose |
|---|---|
| `llm.py` | `ClaudeClient`: the **only** code that calls the Claude API |
| `prompts.py` | **All prompts in one file**, as named constants (e.g. `BILLING_ASSISTANT`). See below. |
| `embedder.py` | `Embedder.embed(text)`: turns a question into a vector with Amazon Titan Text Embeddings V2, the same way the ingestor embeds chunks |
| `retriever.py` | `Retriever.retrieve(query)`: embed → search OpenSearch → return `Passage`s (file, page, text, score) above `RAG_MIN_SCORE` |

## RAG in this folder

RAG = **R**etrieval-**A**ugmented **G**eneration: first find the relevant document passages, then give them to Claude with the question.

```
query ──► embedder.py (Titan V2, 1024 numbers) ──► infra/vector_store.py (kNN search on kb-chunks)
      ──► retriever.py (drop passages scoring < 1.15) ──► list of Passage(file_name, page, text, score)
```

- **Must match the ingestor**: same model, `dimensions=1024`, `normalize=true`, same index. Otherwise the vectors aren't comparable and search returns nonsense.
- **Score** = 1 + cosine similarity. Measured on your documents: on-topic questions 1.27–1.76, off-topic ("hi", "capital of France") ≤ 1.09. The 1.15 cutoff sits in that gap.
- **Errors**: AWS/OpenSearch failures become `RetrievalError`. The service then answers without documents rather than failing the chat.

## llm.py in detail

`ClaudeClient.complete(system, messages)` sends one request to Claude and returns the answer text. `messages` is the conversation so far (from DynamoDB), oldest first, ending with the new question, e.g. `[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, {"role": "user", "content": "..."}]`. Claude itself remembers nothing between requests, so the history is sent each time.

- **Two providers, same code**: `LLM_PROVIDER=bedrock` calls Claude through Amazon Bedrock with your AWS keys (`AsyncAnthropicBedrock`). `LLM_PROVIDER=anthropic` calls the Claude API with an Anthropic key (`AsyncAnthropic`). Both clients have the same `messages.create(...)` interface, so only client creation differs.
- **Model IDs differ per provider**: Bedrock uses e.g. `global.anthropic.claude-haiku-4-5-20251001-v1:0` (`global.` = AWS routes to any region with capacity; `us.`/`eu.` = keep data in that region, about 10% more expensive).
- **Settings** (provider, model, effort, max tokens, keys) come from `.env` via `core/config.py`. `effort` is only sent when `CLAUDE_EFFORT` is set.
- **Errors**: Claude/network errors become one simple `LLMError`, so the rest of the app doesn't need to know Anthropic's error types. The route turns `LLMError` into HTTP `502`.
- **Refusals**: if Claude declines a request, the user gets a polite "can't help" message. For models listed in `FALLBACK_MODELS` (e.g. Sonnet 5.5), the API first retries on a fallback model. Other models (e.g. Haiku) don't support that, so the parameter isn't sent for them.
- **One client for the whole app**: `api/deps.py` creates it once and reuses it, so connections are shared.

## prompts.py in detail

Every prompt is an UPPER_CASE string constant, grouped by section, with a comment saying where it's used:

```python
# Used by: services/chat_service.py, for every chat question
BILLING_ASSISTANT = """..."""
```

Use it anywhere with:

```python
from app.genai.prompts import BILLING_ASSISTANT
```

- **Edit a prompt**: change the text in `prompts.py`; `--reload` restarts the server automatically.
- **Add a prompt**: add a new constant in the right section (create a section if needed), then import it where it's used.
- **Prompt with placeholders**: write `{name}` in the text and fill it in with `MY_PROMPT.format(name=...)`.
- **Why one file**: you can see and compare every prompt the app sends, and prompt changes show up clearly in git diffs.

Current prompts:

| Constant | Role |
|---|---|
| `BILLING_ASSISTANT` | System prompt: support-assistant persona + rules for using documents (facts only from them, never show placeholders like `{{due_date}}` or internal notes, say "contact support" when not covered) |
| `QUESTION_WITH_DOCUMENTS` | Wraps the customer's question with the retrieved passages in `<documents>` / `<question>` tags |
| `DOCUMENT_EXCERPT` | One passage: `<document index source page>text</document>` |
| `NO_DOCUMENTS_FOUND` | Put in `<documents>` when nothing relevant was found |
| `SEARCH_QUERY_REWRITE`, `SEARCH_QUERY_INPUT` | Turn a follow-up ("and for 2 lines?") into a standalone search query, or `NONE` for small talk |

## Why keep it separate?

- Switching models or providers (e.g. Claude via Amazon Bedrock) means changing only this folder.
- Tests replace the service with a fake, so no tokens are spent.

## Later additions

| Idea | Purpose |
|---|---|
| Hybrid search | Combine vector search with keyword search (`text` field), which helps with plan codes and exact names |
| Reranking | Re-score the top ~20 passages with a reranker model before keeping 5 |
