"""Stores chat messages in DynamoDB. The only file that knows about the chat-history table."""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings

logger = logging.getLogger(__name__)


class HistoryError(Exception):
    """Raised when chat history could not be read or written."""


def _secret(value):
    return value.get_secret_value() if value else None


def now_iso() -> str:
    # ISO timestamps with microseconds sort correctly as strings, so SK keeps messages in order
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class ChatHistoryRepository:
    """
    Table layout (one item per message):
      PK = "CONV#<conversation_id>"
      SK = "MSG#<created_at>#<short id>"
      role, content, user_id, tenant_id, created_at, model
    """

    def __init__(self, settings: Settings):
        self._table = settings.chat_table_name
        # boto3 clients are thread-safe, so one client is shared across requests
        self._client = boto3.client(
            "dynamodb",
            region_name=settings.aws_region,
            aws_access_key_id=_secret(settings.aws_access_key_id),
            aws_secret_access_key=_secret(settings.aws_secret_access_key),
        )

    async def get_messages(self, conversation_id: str, limit: int) -> list[dict]:
        """Return the latest `limit` messages, oldest first."""
        return await asyncio.to_thread(self._get_messages, conversation_id, limit)

    async def add_messages(self, conversation_id: str, user_id: str, messages: list[dict]) -> None:
        """Save messages; each needs role, content, created_at and may have model."""
        await asyncio.to_thread(self._add_messages, conversation_id, user_id, messages)

    # boto3 is synchronous, so these run in a worker thread to keep the server responsive.

    def _get_messages(self, conversation_id: str, limit: int) -> list[dict]:
        try:
            response = self._client.query(
                TableName=self._table,
                KeyConditionExpression="PK = :pk AND begins_with(SK, :msg)",
                ExpressionAttributeValues={
                    ":pk": {"S": f"CONV#{conversation_id}"},
                    ":msg": {"S": "MSG#"},
                },
                ScanIndexForward=False,  # newest first, so Limit keeps the latest ones
                Limit=limit,
            )
        except (ClientError, BotoCoreError) as e:
            logger.exception("Could not read chat history")
            raise HistoryError("Could not load chat history") from e

        items = reversed(response["Items"])
        return [
            {"role": i["role"]["S"], "content": i["content"]["S"], "user_id": i["user_id"]["S"]}
            for i in items
        ]

    def _add_messages(self, conversation_id: str, user_id: str, messages: list[dict]) -> None:
        requests = []
        for m in messages:
            item = {
                "PK": {"S": f"CONV#{conversation_id}"},
                "SK": {"S": f"MSG#{m['created_at']}#{uuid.uuid4().hex[:8]}"},
                "role": {"S": m["role"]},
                "content": {"S": m["content"]},
                "user_id": {"S": user_id},
                "tenant_id": {"S": "default"},
                "created_at": {"S": m["created_at"]},
            }
            if m.get("model"):
                item["model"] = {"S": m["model"]}
            requests.append({"PutRequest": {"Item": item}})

        try:
            response = self._client.batch_write_item(RequestItems={self._table: requests})
            if response.get("UnprocessedItems"):
                self._client.batch_write_item(RequestItems=response["UnprocessedItems"])
        except (ClientError, BotoCoreError) as e:
            logger.exception("Could not save chat history")
            raise HistoryError("Could not save chat history") from e
