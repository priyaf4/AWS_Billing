import boto3

from app.core.config import Settings


def make_session(settings: Settings) -> boto3.session.Session:
    """One AWS session for every client (S3, Bedrock, DynamoDB, OpenSearch signing)."""
    return boto3.session.Session(
        aws_access_key_id=_secret(settings.aws_access_key_id),
        aws_secret_access_key=_secret(settings.aws_secret_access_key),
        region_name=settings.aws_region,
    )


def _secret(value):
    return value.get_secret_value() if value else None
