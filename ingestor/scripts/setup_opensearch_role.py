"""
One-time admin setup: create the `rag_ingestor` OpenSearch role and map the ingestor's IAM user to it.

Must run with the OpenSearch MASTER user's AWS keys (fine-grained access control admin).
Safe to run again: it overwrites the role and mapping with the same values.

Usage (from any folder, with a venv that has boto3, e.g. the backend's):
    backend\\.venv\\Scripts\\python ingestor\\scripts\\setup_opensearch_role.py
    ... --env-file <path>   to use keys from a different .env (default: backend/.env)
"""

import argparse
import json
import urllib.error
import urllib.request
from pathlib import Path

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

ENDPOINT = "https://search-rag-opensearch-poc-6vldw2bfgkjhwyp5zvogpb7ami.ap-southeast-2.es.amazonaws.com"
REGION = "ap-southeast-2"
ROLE = "rag_ingestor"
INGESTOR_USER_ARN = "arn:aws:iam::397669520598:user/rag-ingestor-user"
# backend/.env holds the master user's (rag-s3-uploader-user) keys
DEFAULT_ENV_FILE = Path(__file__).resolve().parents[2] / "backend" / ".env"

ROLE_DEFINITION = {
    "description": "RAG ingestor: create and write the kb-chunks index only",
    "cluster_permissions": ["cluster_composite_ops", "cluster_monitor"],
    "index_permissions": [
        {"index_patterns": ["kb-chunks*"], "allowed_actions": ["crud", "create_index", "manage"]}
    ],
}
ROLE_MAPPING = {"users": [INGESTOR_USER_ARN]}


def read_env_file(path):
    values = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"')
    return values


def request(creds, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = AWSRequest(method=method, url=ENDPOINT + path, data=data,
                     headers={"Content-Type": "application/json"})
    SigV4Auth(creds, "es", REGION).add_auth(req)
    http = urllib.request.Request(req.url, data=data, headers=dict(req.headers), method=method)
    try:
        with urllib.request.urlopen(http, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE),
                        help=f".env file holding the master user's AWS keys (default: {DEFAULT_ENV_FILE})")
    env_file = parser.parse_args().env_file
    print("Using keys from:", env_file)
    env = read_env_file(env_file)

    creds = boto3.session.Session(
        aws_access_key_id=env["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=env["AWS_SECRET_ACCESS_KEY"],
        region_name=REGION,
    ).get_credentials()

    status, who = request(creds, "GET", "/_plugins/_security/authinfo")
    if status != 200 or "all_access" not in who.get("roles", []):
        raise SystemExit(f"These keys are not the OpenSearch master user ({status}): {who}")
    print("Signed in as:", who["user_name"])

    for label, path, body in [
        ("Create role", f"/_plugins/_security/api/roles/{ROLE}", ROLE_DEFINITION),
        ("Map user", f"/_plugins/_security/api/rolesmapping/{ROLE}", ROLE_MAPPING),
    ]:
        status, result = request(creds, "PUT", path, body)
        print(f"{label}: {status} {result}")
        if status not in (200, 201):
            raise SystemExit(1)

    status, mapping = request(creds, "GET", f"/_plugins/_security/api/rolesmapping/{ROLE}")
    print("Now mapped:", mapping.get(ROLE, {}).get("users"))


if __name__ == "__main__":
    main()
