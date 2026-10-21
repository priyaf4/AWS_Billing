# app/genai/prompts/

Prompt templates stored as **Markdown files**, separate from code.

## Files

| File | Used by | Purpose |
|---|---|---|
| `__init__.py` | services | `load_prompt("name")` reads `name.md` (cached after first read) |
| `billing_assistant.md` | `ChatService` | System prompt: tells Claude it's a telecom billing support assistant, and how to answer |

## Why files instead of strings in code?

- Non-developers can read and edit the assistant's behaviour.
- Prompt changes show up clearly in git diffs.
- Each version can be tested on its own.

## Editing a prompt

1. Edit the `.md` file.
2. Restart the server. Prompts are cached in memory, and `--reload` only restarts on `.py` changes.
3. Try a few questions on the chat page.

## Adding a prompt

Create `my_prompt.md` here and use `load_prompt("my_prompt")` in a service.
