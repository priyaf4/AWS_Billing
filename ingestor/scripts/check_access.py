"""
Check that the ingestor's AWS keys can reach everything it needs. Read-only except one
tiny Bedrock call (a 1-word embedding, a fraction of a cent).

Usage (from any folder):
    backend\\.venv\\Scripts\\python ingestor\\scripts\\check_access.py
    ... --env-file <path>   (default: ingestor/.env)
"""

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import BotoCoreError, ClientError

DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def read_env_file(path):
    values = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"')
    return values


def check(label, fn):
    try:
        print(f"[OK]   {label}: {fn()}")
        return True
    except (ClientError, BotoCoreError, RuntimeError) as e:
        print(f"[FAIL] {label}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    env = read_env_file(parser.parse_args().env_file)
    region = env["AWS_REGION"]

    session = boto3.session.Session(
        aws_access_key_id=env["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=env["AWS_SECRET_ACCESS_KEY"],
        region_name=region,
    )
    print("Keys belong to:", session.client("sts").get_caller_identity()["Arn"], "\n")

    def s3_list():
        r = session.client("s3").list_objects_v2(
            Bucket=env["S3_BUCKET_NAME"], Prefix=env["S3_UPLOAD_PREFIX"], MaxKeys=5
        )
        return f"{r.get('KeyCount', 0)} file(s) seen, e.g. {[o['Key'] for o in r.get('Contents', [])][:3]}"

    def embed():
        r = session.client("bedrock-runtime").invoke_model(
            modelId=env["EMBEDDING_MODEL"],
            body=json.dumps({"inputText": "hello", "dimensions": int(env["EMBEDDING_DIMENSIONS"])}),
        )
        return f"vector of {len(json.loads(r['body'].read())['embedding'])} numbers"

    def opensearch_whoami():
        req = AWSRequest(method="GET", url=env["OPENSEARCH_ENDPOINT"] + "/_plugins/_security/authinfo")
        SigV4Auth(session.get_credentials(), "es", region).add_auth(req)
        try:
            with urllib.request.urlopen(
                urllib.request.Request(req.url, headers=dict(req.headers)), timeout=20
            ) as r:
                body = json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode()[:200]}") from e
        return f"OpenSearch roles = {body.get('roles')}"

    def dynamo_read():
        session.client("dynamodb").get_item(
            TableName=env["DOCUMENTS_TABLE_NAME"], Key={"PK": {"S": "DOC#access-check"}}
        )
        return f"table '{env['DOCUMENTS_TABLE_NAME']}' readable"

    results = [
        check("S3 read uploads", s3_list),
        check("Bedrock Titan embeddings", embed),
        check("OpenSearch role mapping", opensearch_whoami),
        check("DynamoDB documents table", dynamo_read),
    ]
    print(f"\n{sum(results)}/{len(results)} checks passed")


if __name__ == "__main__":
    main()
