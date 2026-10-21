# app/genai/

Everything specific to **AI / LLMs** lives here, so it's all in one place.

## Files

| File / folder | Purpose |
|---|---|
| `llm.py` | `ClaudeClient`: the **only** code that calls the Claude API |
| `prompts.py` | **All prompts in one file**, as named constants (e.g. `BILLING_ASSISTANT`). See below. |

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

## Why keep it separate?

- Switching models or providers (e.g. Claude via Amazon Bedrock) means changing only this folder.
- Tests replace the service with a fake, so no tokens are spent.

## Later additions

| File | Purpose |
|---|---|
| `embeddings.py` | Turn text chunks into vectors |
| `retriever.py` | Find the most relevant PDF chunks for a question |
