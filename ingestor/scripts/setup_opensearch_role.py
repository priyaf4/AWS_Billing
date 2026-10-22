"""
One-time admin setup: create the OpenSearch roles and map AWS identities to them.

  rag_ingestor  write kb-chunks*   mapped to the ingestor's IAM user (+ its ECS task role, if given)
  rag_reader    search kb-chunks*  mapped to the backend's ECS task role (if given)

Must run with the OpenSearch MASTER user's AWS keys (fine-grained access control admin).
Safe to run again: roles are rewritten with the same values, and mappings are ADDED to (existing users and
backend roles are kept), so running with only --backend-task-role-arn doesn't undo an earlier ingestor mapping.

Usage (from any folder, with a venv that has boto3, e.g. the backend's):
    backend\\.venv\\Scripts\\python ingestor\\scripts\\setup_opensearch_role.py
    ... --env-file <path>   to use keys from a different .env (default: backend/.env)
    ... --ingestor-task-role-arn <arn> --backend-task-role-arn <arn>   for the ECS deployment
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
READER_ROLE = "rag_reader"
READER_ROLE_DEFINITION = {
    "description": "Chat backend: search the kb-chunks index only",
    "cluster_permissions": ["cluster_composite_ops_ro"],
    "index_permissions": [{"index_patterns": ["kb-chunks*"], "allowed_actions": ["read"]}],
}


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


def merged_mapping(creds, role, users=(), backend_roles=()):
    """The role's current mapping plus the given users and backend roles, so a PUT never drops existing entries."""
    status, current = request(creds, "GET", f"/_plugins/_security/api/rolesmapping/{role}")
    if status == 200:
        existing = current.get(role, {})
    elif status == 404:  # role not mapped yet
        existing = {}
    else:
        raise SystemExit(f"Could not read the current mapping of {role} ({status}): {str(current)[:200]}")
    return {
        "users": sorted(set(existing.get("users", [])) | set(users)),
        "backend_roles": sorted(set(existing.get("backend_roles", [])) | set(backend_roles)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE),
                        help=f".env file holding the master user's AWS keys (default: {DEFAULT_ENV_FILE})")
    # IAM roles are mapped as OpenSearch "backend roles"; IAM users as "users"
    parser.add_argument("--ingestor-task-role-arn", help="ECS task role of the ingestor (gets write access)")
    parser.add_argument("--backend-task-role-arn", help="ECS task role of the chat backend (gets search access)")
    args = parser.parse_args()
    env_file = args.env_file
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

    ingestor_roles = [args.ingestor_task_role_arn] if args.ingestor_task_role_arn else []
    steps = [
        ("Create role", f"/_plugins/_security/api/roles/{ROLE}", ROLE_DEFINITION),
        ("Map ingestor", f"/_plugins/_security/api/rolesmapping/{ROLE}",
         merged_mapping(creds, ROLE, users=[INGESTOR_USER_ARN], backend_roles=ingestor_roles)),
    ]
    if args.backend_task_role_arn:
        steps += [
            ("Create reader role", f"/_plugins/_security/api/roles/{READER_ROLE}", READER_ROLE_DEFINITION),
            ("Map backend", f"/_plugins/_security/api/rolesmapping/{READER_ROLE}",
             merged_mapping(creds, READER_ROLE, backend_roles=[args.backend_task_role_arn])),
        ]

    for label, path, body in steps:
        status, result = request(creds, "PUT", path, body)
        print(f"{label}: {status} {result}")
        if status not in (200, 201):
            raise SystemExit(1)

    for role in (ROLE, READER_ROLE):
        status, mapping = request(creds, "GET", f"/_plugins/_security/api/rolesmapping/{role}")
        if status == 200:
            print(f"Now mapped to {role}:", mapping.get(role))


if __name__ == "__main__":
    main()
