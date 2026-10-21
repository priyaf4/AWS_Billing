"""Reads uploaded files from S3."""

import boto3

from app.core.config import Settings


class FileTooLarge(Exception):
    pass


class FileStore:
    def __init__(self, settings: Settings, session: boto3.session.Session):
        self._client = session.client("s3")
        self._bucket = settings.s3_bucket_name
        self._max_bytes = settings.max_file_mb * 1024 * 1024

    def read(self, key: str) -> bytes:
        obj = self._client.get_object(Bucket=self._bucket, Key=key)
        if obj["ContentLength"] > self._max_bytes:
            obj["Body"].close()
            raise FileTooLarge(f"File is larger than {self._max_bytes // (1024 * 1024)} MB")
        return obj["Body"].read()
