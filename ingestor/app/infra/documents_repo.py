"""Tracks each uploaded file's ingestion status in the DynamoDB `documents` table."""

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings

_serialize = TypeSerializer().serialize
_deserialize = TypeDeserializer().deserialize


class RepositoryError(Exception):
    pass


class DocumentsRepository:
    """
    One item per file:  PK = "DOC#<doc_id>"
    plus doc_id, file_name, s3_key, status (pending | processing | ready | failed),
    updated_at, and when known: chunk_count, page_count, error.
    """

    def __init__(self, settings: Settings, session: boto3.session.Session):
        self._table = settings.documents_table_name
        self._client = session.client("dynamodb")

    def save(self, record: dict) -> None:
        item = {"PK": f"DOC#{record['doc_id']}", **{k: v for k, v in record.items() if v is not None}}
        try:
            self._client.put_item(TableName=self._table, Item={k: _serialize(v) for k, v in item.items()})
        except (ClientError, BotoCoreError) as e:
            raise RepositoryError("Could not save document status") from e

    def get(self, doc_id: str) -> dict | None:
        try:
            response = self._client.get_item(TableName=self._table, Key={"PK": {"S": f"DOC#{doc_id}"}})
        except (ClientError, BotoCoreError) as e:
            raise RepositoryError("Could not load document status") from e
        return _to_record(response["Item"]) if "Item" in response else None

    def list_all(self) -> list[dict]:
        """Fine for hundreds of files. With many tenants, switch to a Query on a tenant key."""
        try:
            pages = self._client.get_paginator("scan").paginate(TableName=self._table)
            return [_to_record(item) for page in pages for item in page["Items"]]
        except (ClientError, BotoCoreError) as e:
            raise RepositoryError("Could not list documents") from e


def _to_record(item: dict) -> dict:
    record = {k: _deserialize(v) for k, v in item.items() if k != "PK"}
    for key in ("chunk_count", "page_count"):  # DynamoDB numbers come back as Decimal
        if key in record:
            record[key] = int(record[key])
    return record
