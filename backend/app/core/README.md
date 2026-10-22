# app/core/

Shared basics that every other layer can use.

## Files

| File | Purpose |
|---|---|
| `config.py` | `Settings`: reads configuration from environment variables and `.env`. `get_settings()` returns one cached copy. |
| `aws.py` | `make_session()`: one boto3 session with the backend's AWS keys, used for Titan embeddings and OpenSearch signing |

## How config works

Each field in `Settings` maps to an env var (case-insensitive):

| Field | Env var | Default |
|---|---|---|
| `llm_provider` | `LLM_PROVIDER` | `bedrock` (or `anthropic`) |
| `aws_region` | `AWS_REGION` | `us-east-1` |
| `aws_access_key_id` | `AWS_ACCESS_KEY_ID` | empty → default AWS credential chain |
| `aws_secret_access_key` | `AWS_SECRET_ACCESS_KEY` | empty → default AWS credential chain |
| `anthropic_api_key` | `ANTHROPIC_API_KEY` | only needed when `LLM_PROVIDER=anthropic` |
| `claude_model` | `CLAUDE_MODEL` | `global.anthropic.claude-haiku-4-5-20251001-v1:0` |
| `claude_effort` | `CLAUDE_EFFORT` | empty (not sent; Haiku 4.5 doesn't support it) |
| `claude_max_tokens` | `CLAUDE_MAX_TOKENS` | `4000` |

To add a setting: add a field to `Settings`, document it in `.env.example`, and read it with `get_settings().<field>`.

Keys are `SecretStr`, so they aren't printed if settings get logged.
In production (Docker/AWS), the same variables are set by the platform instead of a `.env` file. No code changes needed.

## Later additions

| File | Purpose |
|---|---|
| `security.py` | Password hashing, JWT tokens (authentication) |
| `logging.py` | Structured logging setup |
| `exceptions.py` | App-wide error types and handlers |
