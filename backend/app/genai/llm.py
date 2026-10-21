"""The only file that talks to Claude. Swap providers by changing this file."""

import logging

import anthropic

from app.core.config import Settings

logger = logging.getLogger(__name__)

REFUSAL_REPLY = "Sorry, I can't help with that request."

# Models that accept the server-side refusal fallback (Claude API only, not Bedrock).
FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}


class LLMError(Exception):
    """Raised when the LLM could not produce an answer."""


def _secret(value):
    return value.get_secret_value() if value else None


def _make_client(settings: Settings):
    if settings.llm_provider == "bedrock":
        return anthropic.AsyncAnthropicBedrock(
            aws_region=settings.aws_region,
            aws_access_key=_secret(settings.aws_access_key_id),
            aws_secret_key=_secret(settings.aws_secret_access_key),
        )
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
    return anthropic.AsyncAnthropic(api_key=_secret(settings.anthropic_api_key))


class ClaudeClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = _make_client(settings)

    @property
    def model(self) -> str:
        return self._settings.claude_model

    async def complete(self, system: str, messages: list[dict]) -> str:
        """`messages` is the conversation so far, oldest first, ending with the user's question."""
        s = self._settings
        params = {
            "model": s.claude_model,
            "max_tokens": s.claude_max_tokens,
            "system": system,
            "messages": messages,
        }
        if s.claude_effort:
            params["output_config"] = {"effort": s.claude_effort}

        try:
            if s.llm_provider == "anthropic" and s.claude_model in FALLBACK_MODELS:
                # If the model declines, the API retries on a fallback model in the same call.
                response = await self._client.beta.messages.create(
                    **params, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
                )
            else:
                response = await self._client.messages.create(**params)
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
            logger.error("LLM credentials rejected or model access not enabled: %s", e)
            raise LLMError("LLM is not configured correctly") from e
        except anthropic.RateLimitError as e:
            raise LLMError("LLM is busy, please try again shortly") from e
        except anthropic.APIStatusError as e:
            logger.exception("LLM returned %s", e.status_code)
            raise LLMError("LLM request failed") from e
        except anthropic.APIConnectionError as e:
            logger.exception("Could not reach the LLM")
            raise LLMError("Could not reach the LLM") from e

        if response.stop_reason == "refusal":
            return REFUSAL_REPLY
        return "".join(block.text for block in response.content if block.type == "text")
