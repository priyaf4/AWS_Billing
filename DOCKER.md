# Docker images and AWS deployment

Three images, one per service. Each folder has its own `Dockerfile` and `.dockerignore`.

| Image | Folder | Container port | Health check | Reachable from |
|---|---|---|---|---|
| `genai-frontend` | `frontend/` | 3000 | `GET /` | Internet (behind a load balancer) |
| `genai-backend` | `backend/` | 8000 | `GET /health` | Frontend only (private) |
| `rag-ingestor` | `ingestor/` | 8002 | `GET /health` | Frontend only (private) |

**No secrets are inside the images.** `.env` files are excluded by `.dockerignore`, and all configuration is read
from environment variables when the container starts.

## Build

From the repo root (`E:\CrackedGoogle2026\Projects\aws`):

```powershell
docker build --platform linux/amd64 -t genai-frontend:latest frontend
docker build --platform linux/amd64 -t genai-backend:latest  backend
docker build --platform linux/amd64 -t rag-ingestor:latest   ingestor
```

`--platform linux/amd64` matches AWS Fargate's default CPU type. For Graviton (ARM) tasks, use `linux/arm64` instead.

## Test locally before pushing

```powershell
docker compose up --build
```

Then open http://localhost:3000. This runs the same three images, each reading its own `.env` file, with the
frontend pointed at the other containers by name (`http://backend:8000`, `http://ingestor:8002`).
Stop the local `uvicorn` / `npm run dev` processes first, or the ports clash.

## Push to Amazon ECR

One-time: create a repository per image (region `ap-southeast-2`):

```powershell
aws ecr create-repository --repository-name genai-frontend --region ap-southeast-2
aws ecr create-repository --repository-name genai-backend  --region ap-southeast-2
aws ecr create-repository --repository-name rag-ingestor   --region ap-southeast-2
```

Each time you push:

```powershell
$REGISTRY = "397669520598.dkr.ecr.ap-southeast-2.amazonaws.com"
aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin $REGISTRY

foreach ($img in "genai-frontend", "genai-backend", "rag-ingestor") {
  docker tag  "${img}:latest" "$REGISTRY/${img}:latest"
  docker push "$REGISTRY/${img}:latest"
}
```

Tip: also tag with a version (e.g. the git commit, `:a1b2c3d`), so a deployment can be rolled back to an exact image.

## Environment variables per container

Set these in the ECS task definition (or App Runner service). Put secrets in **AWS Secrets Manager** or
**SSM Parameter Store** and reference them, rather than typing them in as plain values.

### genai-frontend

| Variable | Example | Secret? |
|---|---|---|
| `BACKEND_URL` | `http://backend.genai.local:8000` (internal address of the backend) | |
| `INGESTOR_URL` | `http://ingestor.genai.local:8002` | |
| `AWS_REGION`, `S3_BUCKET_NAME` | `ap-southeast-2`, `priya-genai-rag-docs-2026` | |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | | ✅ password |
| `AUTH_SECRET` | long random string (signs the login cookie) | ✅ **must be set**, or a weak dev default is used |
| `COOKIE_SECURE` | leave unset with HTTPS; `false` only while testing over plain `http://` | |

### genai-backend

Everything in `backend/.env.example`: `LLM_PROVIDER=bedrock`, `AWS_REGION`, `CLAUDE_MODEL`, `CLAUDE_EFFORT` (empty),
`CLAUDE_MAX_TOKENS`, `CHAT_TABLE_NAME`, `CHAT_HISTORY_LIMIT`, `OPENSEARCH_ENDPOINT`, `OPENSEARCH_INDEX`,
`EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`, `RAG_TOP_K`, `RAG_MIN_SCORE`.

### rag-ingestor

Everything in `ingestor/.env.example`: `AWS_REGION`, `S3_BUCKET_NAME`, `S3_UPLOAD_PREFIX`, `MAX_FILE_MB`, `CHUNK_SIZE`,
`CHUNK_OVERLAP`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`, `EMBEDDING_CONCURRENCY`, `OPENSEARCH_ENDPOINT`,
`OPENSEARCH_INDEX`, `DOCUMENTS_TABLE_NAME`.

## AWS credentials: use task roles, not access keys

On AWS, **don't set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`**. Give each ECS task an **IAM task role**; the
AWS SDKs in all three services pick it up automatically. Each role needs what its IAM user has today:

| Task role | Permissions (same as today's policies) |
|---|---|
| frontend | S3 `PutObject` / `GetObject` / `ListBucket` on `priya-genai-rag-docs-2026` (`uploads/`) |
| backend | Bedrock `InvokeModel` on Claude Haiku 4.5 **and** Titan Text Embeddings V2; DynamoDB on `chat-history`; `es:ESHttp*` on the domain |
| ingestor | the `RagIngestorPolicy` (S3 read, Titan, `es:ESHttp*`, DynamoDB `documents`) |

**OpenSearch needs two extra steps for roles:**
1. Add the backend and ingestor **role ARNs** to the domain's access policy (today it lists the two IAM users).
2. Map the role ARNs inside OpenSearch, as **backend roles**: the ingestor role → `rag_ingestor`, and the backend
   role → a read-only role on `kb-chunks*`. (IAM *users* are mapped as users; IAM *roles* as backend roles.)

## Networking

```
Internet ──HTTPS──► Load balancer ──► genai-frontend (3000)
                                           │  private network only
                                           ├──► genai-backend (8000)
                                           └──► rag-ingestor  (8002)
```

- Only the frontend is public. The backend trusts the `X-User-Id` header from the frontend, so it **must not** be
  reachable from the internet. Use ECS Service Connect or Cloud Map so the frontend reaches it by an internal name.
- Point the load balancer health checks at the paths in the table at the top.
- Use HTTPS (an ACM certificate on the load balancer). The login cookie is `Secure` in production.

## Operational notes

- **Ingestor:** files are processed in the background inside the container. Keep at least 1 task running, and
  don't stop tasks while a file shows "Indexing...". (Moving to an SQS queue later removes this limitation.)
- **Logs:** all three write to stdout, so the ECS `awslogs` driver sends them to CloudWatch with no extra setup.
- **Scaling:** each container runs a single server process; scale by adding tasks.
