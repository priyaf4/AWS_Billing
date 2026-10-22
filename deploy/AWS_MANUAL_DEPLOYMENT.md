# Deploy DeskCopilot to AWS by hand (console)

A click-by-click guide to run the three containers (frontend, backend, ingestor) on **ECS Fargate**.
Everything is in **Sydney (ap-southeast-2)**. Before you start, check the region selector in the top-right of the AWS console on every page.

The end result:

```
Browser ──HTTP(S)──► Application Load Balancer ──► frontend (port 3000)   public
                                                       │ Service Connect (private)
                                          ┌────────────┴────────────┐
                                          ▼                         ▼
                                   backend :8000              ingestor :8002   private
                                          │                         │
                       Bedrock, DynamoDB chat-history,     S3, Bedrock Titan, DynamoDB documents,
                       OpenSearch (search)                 OpenSearch (write)
```

> AWS renames console buttons from time to time. If a label differs slightly, look for the closest match.

---

## 0. Before you start

**Tools on your PC:** Docker Desktop (running) and the AWS CLI (`aws --version`).
The CLI must be logged in as a user allowed to push to ECR: run `aws configure`, then check with `aws sts get-caller-identity`.

**Values used throughout this guide:**

| Name | Value |
|---|---|
| Account ID | `397669520598` |
| Region | `ap-southeast-2` |
| S3 bucket | `priya-genai-rag-docs-2026` |
| OpenSearch domain | `rag-opensearch-poc` |
| OpenSearch endpoint | `https://search-rag-opensearch-poc-6vldw2bfgkjhwyp5zvogpb7ami.ap-southeast-2.es.amazonaws.com` |
| DynamoDB tables | `chat-history` (backend), `documents` (ingestor) |
| ECR registry | `397669520598.dkr.ecr.ap-southeast-2.amazonaws.com` |
| ECS namespace | `deskcopilot` |

**Generate a login secret now and keep it somewhere safe** (it signs the login cookie):

```powershell
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

Also choose a strong `ADMIN_PASSWORD`. Don't keep `admin`/`admin` on the internet.

> **About secrets:** this guide puts `ADMIN_PASSWORD` and `AUTH_SECRET` directly in the task definitions as plain environment variables, instead of using Secrets Manager.
> That works, but anyone who can open your ECS task definitions in the console can read them. Only give ECS console access to people you trust.

---

## 1. Push the three images to ECR

ECR (Elastic Container Registry) is where ECS downloads your images from.

### 1.1 Create three repositories
Console: **ECR → Private registry → Repositories → Create repository**. Create each of these, keeping the default settings:

- `rag-frontend`
- `rag-chat-api` (the backend)
- `rag-ingestor`

### 1.2 Build and push (PowerShell, in the project root)

```powershell
$REG = "397669520598.dkr.ecr.ap-southeast-2.amazonaws.com"

# Log Docker in to ECR (valid for 12 hours)
aws ecr get-login-password --region ap-southeast-2 | docker login --username AWS --password-stdin $REG

# Build all three (same images docker-compose runs locally)
docker compose build

# local image name -> ECR repository name
$images = @{ "genai-frontend" = "rag-frontend"; "genai-backend" = "rag-chat-api"; "rag-ingestor" = "rag-ingestor" }
foreach ($local in $images.Keys) {
  $repo = $images[$local]
  docker tag "${local}:latest" "$REG/${repo}:latest"
  docker push "$REG/${repo}:latest"
}
```

Check: each repository in the ECR console now shows a `latest` image.

> Every repository also has a **View push commands** button that shows these same commands.

---

## 2. Security groups (firewall rules)

This guide uses your account's **default VPC**. Every region has one, and its subnets are public.
The containers get a public IP so they can download images and call AWS services without a NAT gateway (a NAT gateway costs about $45/month).
The security groups below still block every incoming connection you don't explicitly allow.

Console: **EC2 → Network & Security → Security Groups → Create security group**. VPC: the default one (named `-` or "default").

Create these three groups, in this order:

| Name | Inbound rule(s) | Why |
|---|---|---|
| `deskcopilot-alb-sg` | HTTP, port 80, source `0.0.0.0/0` (add HTTPS 443 later, in step 9) | The load balancer is the only public entry point |
| `deskcopilot-frontend-sg` | Custom TCP, port **3000**, source **`deskcopilot-alb-sg`** (start typing `sg-` and pick it) | Only the load balancer can reach the frontend |
| `deskcopilot-internal-sg` | Custom TCP, port **8000**, source **`deskcopilot-frontend-sg`**<br>Custom TCP, port **8002**, source **`deskcopilot-frontend-sg`** | Only the frontend can reach the backend and ingestor |

Leave the outbound rules at their default (all traffic allowed).

> **Why this matters:** the backend trusts the `X-User-Id` header that the frontend sends.
> If anyone else could reach port 8000, they could pretend to be any user. `deskcopilot-internal-sg` is what prevents that.

---

## 3. IAM roles (instead of access keys)

ECS needs two kinds of roles:

- **Task execution role:** lets ECS itself download your image from ECR and write logs. One role is shared by all three apps.
- **Task role:** what *your code* is allowed to do (S3, Bedrock, DynamoDB, OpenSearch). One per app.

The code already falls back to the task role when no access keys are set.
**Do not add `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` to any task definition, not even empty ones.**

### 3.1 Task execution role
Nothing to do now. When you create the first task definition (step 5), choose **Create new role** and ECS creates `ecsTaskExecutionRole` for you. Pick that same role for the other two task definitions.

### 3.2 Create the three task roles
For each role:

1. **IAM → Roles → Create role**.
2. Trusted entity type: **AWS service**. Service or use case: **Elastic Container Service**. Use case: **Elastic Container Service Task**. Click **Next**.
3. Skip the permissions page (**Next**), enter the role name, then **Create role**.
4. Open the new role → **Add permissions → Create inline policy → JSON**. Paste the policy below, click **Next**, name it (e.g. `app-access`), then **Create policy**.
5. Copy the role's **ARN** from the role summary page. You need the backend and ingestor ARNs in step 4.

#### `deskcopilot-frontend-task-role`
Lists, uploads and downloads files in the bucket.
```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "ListBucket", "Effect": "Allow", "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::priya-genai-rag-docs-2026" },
    { "Sid": "ReadWriteFiles", "Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::priya-genai-rag-docs-2026/*" }
  ]
}
```

#### `deskcopilot-backend-task-role`
Calls Claude and Titan, reads and writes chat history, and searches OpenSearch.
```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "Bedrock", "Effect": "Allow",
      "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
      "Resource": [
        "arn:aws:bedrock:ap-southeast-2:397669520598:inference-profile/global.anthropic.claude-haiku-4-5-20251001-v1:0",
        "arn:aws:bedrock:*::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0",
        "arn:aws:bedrock:::foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0",
        "arn:aws:bedrock:ap-southeast-2::foundation-model/amazon.titan-embed-text-v2:0"
      ] },
    { "Sid": "ChatHistory", "Effect": "Allow",
      "Action": ["dynamodb:Query", "dynamodb:BatchWriteItem", "dynamodb:GetItem", "dynamodb:PutItem"],
      "Resource": [
        "arn:aws:dynamodb:ap-southeast-2:397669520598:table/chat-history",
        "arn:aws:dynamodb:ap-southeast-2:397669520598:table/chat-history/index/*"
      ] },
    { "Sid": "OpenSearch", "Effect": "Allow",
      "Action": ["es:ESHttpGet", "es:ESHttpHead", "es:ESHttpPost"],
      "Resource": "arn:aws:es:ap-southeast-2:397669520598:domain/rag-opensearch-poc/*" }
  ]
}
```

#### `deskcopilot-ingestor-task-role`
Reads uploaded files, creates embeddings, writes to OpenSearch, and records file status.
```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "ReadFiles", "Effect": "Allow", "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::priya-genai-rag-docs-2026/*" },
    { "Sid": "ListBucket", "Effect": "Allow", "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::priya-genai-rag-docs-2026" },
    { "Sid": "Embeddings", "Effect": "Allow", "Action": "bedrock:InvokeModel",
      "Resource": "arn:aws:bedrock:ap-southeast-2::foundation-model/amazon.titan-embed-text-v2:0" },
    { "Sid": "DocumentStatus", "Effect": "Allow",
      "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query", "dynamodb:Scan"],
      "Resource": [
        "arn:aws:dynamodb:ap-southeast-2:397669520598:table/documents",
        "arn:aws:dynamodb:ap-southeast-2:397669520598:table/documents/index/*"
      ] },
    { "Sid": "OpenSearch", "Effect": "Allow",
      "Action": ["es:ESHttpGet", "es:ESHttpHead", "es:ESHttpPost", "es:ESHttpPut", "es:ESHttpDelete"],
      "Resource": "arn:aws:es:ap-southeast-2:397669520598:domain/rag-opensearch-poc/*" }
  ]
}
```

> **These roles should do what your current IAM users already do.** If a call later fails with `AccessDenied`, compare the role with the user that works locally:
> **IAM → Users → (user) → Permissions** shows its policies.
> Claude through the `global.` inference profile is the most likely mismatch; copy the user's Bedrock statement if it differs.

---

## 4. Give the roles access to OpenSearch

OpenSearch checks every request **twice**, and both checks must pass or you get `403` errors:

1. **The domain access policy** (an AWS-level rule) must allow the role.
2. **Fine-grained access control** (OpenSearch's own users and roles) must map the role to an OpenSearch role.

### 4.1 Domain access policy
Console: **Amazon OpenSearch Service → Domains → rag-opensearch-poc → Security configuration → Edit**, then scroll to **Access policy**.

- If the policy's `Principal` is `"AWS": "*"` or `"AWS": "arn:aws:iam::397669520598:root"`, **you don't need to change anything**. That already allows any identity in your account that has `es:ESHttp*` in its IAM policy, which the roles from step 3 do.
- If it lists specific user ARNs instead, add the two role ARNs to the same `Principal` list, then **Save changes**:

```json
"Principal": { "AWS": [
  "arn:aws:iam::397669520598:user/rag-ingestor-user",
  "arn:aws:iam::397669520598:role/deskcopilot-backend-task-role",
  "arn:aws:iam::397669520598:role/deskcopilot-ingestor-task-role"
] }
```

### 4.2 Fine-grained mapping (run the script)
The domain's master user is an IAM user, so the OpenSearch Dashboards web UI isn't easy to log in to. Use the existing setup script instead; it now accepts the role ARNs.
It must run with the **master user's** keys (by default it reads them from `backend/.env`):

```powershell
cd E:\CrackedGoogle2026\Projects\aws
backend\.venv\Scripts\python ingestor\scripts\setup_opensearch_role.py `
  --ingestor-task-role-arn arn:aws:iam::397669520598:role/deskcopilot-ingestor-task-role `
  --backend-task-role-arn  arn:aws:iam::397669520598:role/deskcopilot-backend-task-role
```

It:
- maps the **ingestor role** to `rag_ingestor` (write access to `kb-chunks*`);
- creates a read-only `rag_reader` role and maps the **backend role** to it (search only).

The script ends by printing both mappings. Check that the two role ARNs appear under `backend_roles`.

> **The local backend is not affected.** It uses the master user's keys, which already have full access.

---

## 5. ECS cluster and task definitions

### 5.1 Create the cluster
**ECS → Clusters → Create cluster**:
- Cluster name: `deskcopilot`
- **Service Connect defaults → Default namespace:** `deskcopilot`. This creates a private name directory in AWS Cloud Map, so the frontend can reach the other services as `http://backend:8000` and `http://ingestor:8002`.
- Infrastructure: **AWS Fargate (serverless)** only.
- Create.

### 5.2 Create the three task definitions
**ECS → Task definitions → Create new task definition** (the form, not JSON). Use the same settings for all three, except where the table says otherwise:

- Launch type: **AWS Fargate**
- Operating system/Architecture: **Linux/X86_64**. Images built on Windows are x86; picking ARM gives an `exec format error`.
- Task execution role: **Create new role** the first time, then `ecsTaskExecutionRole`.
- Container: **Essential = Yes**.
- Logging: leave **Use log collection** on (Amazon CloudWatch). Logs go to `/ecs/<family>`.

| Setting | Backend | Ingestor | Frontend |
|---|---|---|---|
| Task definition family | `deskcopilot-backend` | `deskcopilot-ingestor` | `deskcopilot-frontend` |
| CPU / Memory | 0.5 vCPU / 1 GB | 1 vCPU / 2 GB (PDF parsing and embedding) | 0.5 vCPU / 1 GB |
| Task role | `deskcopilot-backend-task-role` | `deskcopilot-ingestor-task-role` | `deskcopilot-frontend-task-role` |
| Container name | `backend` | `ingestor` | `frontend` |
| Image URI | `397669520598.dkr.ecr.ap-southeast-2.amazonaws.com/rag-chat-api:latest` | `.../rag-ingestor:latest` | `.../rag-frontend:latest` |
| Port mapping: container port | `8000` | `8002` | `3000` |
| Port mapping: **port name** | `backend` | `ingestor` | `frontend` |
| Port mapping: app protocol | HTTP | HTTP | HTTP |

The **port name** matters: Service Connect looks the port up by this name in step 7.

**Environment variables.** Add each one with **Add environment variable** (Type: Value).

Backend:

| Key | Value |
|---|---|
| `LLM_PROVIDER` | `bedrock` |
| `AWS_REGION` | `ap-southeast-2` |
| `CLAUDE_MODEL` | `global.anthropic.claude-haiku-4-5-20251001-v1:0` |
| `CLAUDE_MAX_TOKENS` | `4000` |
| `CHAT_TABLE_NAME` | `chat-history` |
| `CHAT_HISTORY_LIMIT` | `20` |
| `OPENSEARCH_ENDPOINT` | the endpoint from step 0 |
| `OPENSEARCH_INDEX` | `kb-chunks` |
| `EMBEDDING_MODEL` | `amazon.titan-embed-text-v2:0` |
| `EMBEDDING_DIMENSIONS` | `1024` |

Ingestor:

| Key | Value |
|---|---|
| `AWS_REGION` | `ap-southeast-2` |
| `S3_BUCKET_NAME` | `priya-genai-rag-docs-2026` |
| `S3_UPLOAD_PREFIX` | `uploads/` |
| `EMBEDDING_MODEL` | `amazon.titan-embed-text-v2:0` |
| `EMBEDDING_DIMENSIONS` | `1024` |
| `OPENSEARCH_ENDPOINT` | the endpoint from step 0 |
| `OPENSEARCH_INDEX` | `kb-chunks` |
| `DOCUMENTS_TABLE_NAME` | `documents` |

Frontend:

| Key | Value |
|---|---|
| `BACKEND_URL` | `http://backend:8000` |
| `INGESTOR_URL` | `http://ingestor:8002` |
| `AWS_REGION` | `ap-southeast-2` |
| `S3_BUCKET_NAME` | `priya-genai-rag-docs-2026` |
| `ADMIN_USERNAME` | `admin` (or your choice) |
| `ADMIN_PASSWORD` | your strong password |
| `AUTH_SECRET` | the 64-character value from step 0 (if it isn't set, a weak built-in default is used) |
| `COOKIE_SECURE` | `false`, **only until HTTPS works** (step 9) |

> Compare these with your local `backend/.env` and `ingestor/.env`. If you've added other settings there, add them here too, except the AWS keys.

---

## 6. Load balancer

Create the load balancer and its target group before the frontend service, so the service can attach to them.

### 6.1 Target group
**EC2 → Load Balancing → Target Groups → Create target group**:
- Target type: **IP addresses** (Fargate requires this).
- Name: `deskcopilot-frontend-tg`. Protocol **HTTP**, port **3000**. VPC: default.
- Health check path: `/`. Under **Advanced health check settings**, set success codes to `200-399`.
- Next. **Don't register any targets** (ECS does that). Create.

### 6.2 Application Load Balancer
**EC2 → Load Balancers → Create load balancer → Application Load Balancer**:
- Name: `deskcopilot-alb`. Scheme: **Internet-facing**. IP address type: IPv4.
- Network mapping: default VPC; tick **at least two** availability zones (tick all of them).
- Security groups: **remove `default`** and select `deskcopilot-alb-sg`.
- Listeners: **HTTP : 80**, forwarding to `deskcopilot-frontend-tg`.
- Create. After a few minutes, its state changes to *Active*. Copy its **DNS name** (e.g. `deskcopilot-alb-123456.ap-southeast-2.elb.amazonaws.com`).

---

## 7. Create the three services

**ECS → Clusters → deskcopilot → Services → Create**. Create the **backend and ingestor first**, then the frontend.

Settings common to all three:
- Compute options: **Launch type**, FARGATE, platform version LATEST.
- Application type: **Service**. Task definition: the matching family, latest revision.
- Desired tasks: **1**.
- **Networking:** VPC default, all subnets, **public IP: turned on** (it needs this to pull images without a NAT gateway). Security group: **remove `default`** and choose the group listed below.

| | Backend | Ingestor | Frontend |
|---|---|---|---|
| Service name | `backend` | `ingestor` | `frontend` |
| Security group | `deskcopilot-internal-sg` | `deskcopilot-internal-sg` | `deskcopilot-frontend-sg` |
| **Service Connect** | Turn on. **Client and server**. Namespace `deskcopilot`. Add port mapping: port alias `backend`, discovery name `backend`, DNS `backend`, port `8000` | Turn on. **Client and server**. Namespace `deskcopilot`. Port alias `ingestor`, discovery `ingestor`, DNS `ingestor`, port `8002` | Turn on. **Client side only**. Namespace `deskcopilot` |
| Load balancing | None | None | **Application Load Balancer → Use an existing load balancer** `deskcopilot-alb` → listener **80:HTTP** → **existing target group** `deskcopilot-frontend-tg`. Health check grace period: **60** seconds |

> **Why the ingestor uses "client and server" too:** it's a server (the frontend calls it).
> The frontend is only a client of the other two, and it's reached through the load balancer instead.

After creating each service, open it → **Tasks**. Wait until the task shows **Running**. If it stops, open the stopped task and read **Stopped reason** (see step 11).

---

## 8. Test over plain HTTP

1. Open `http://<ALB DNS name>` from step 6.2 in your browser.
2. Log in with your new `ADMIN_PASSWORD`. This only works because `COOKIE_SECURE=false`.
3. **Chat:** send a message. A reply means frontend → backend → Bedrock → DynamoDB → OpenSearch all work.
4. **File Storage:** upload a small PDF. It should go from *Indexing...* to *Ready (N chunks)*. That means frontend → S3 → ingestor → Titan → OpenSearch → DynamoDB all work.
5. **Check the backend is private:** EC2 → Network Interfaces → find the backend task's public IP, then open `http://<that-ip>:8000/health`. It must **time out**. If it answers, `deskcopilot-internal-sg` is wrong.

---

## 9. Turn on HTTPS

Plain HTTP sends your password unencrypted, so do this before sharing the link. There are two options.

### Option A: you own a domain name (recommended)
1. **Certificate Manager (ACM)**, in **ap-southeast-2** → Request → Public certificate → domain e.g. `app.yourdomain.com` → **DNS validation**.
   Add the CNAME record it shows to your domain's DNS. If the domain is in Route 53, click **Create records in Route 53**. Wait for the status to become *Issued*.
2. **EC2 → Security Groups → `deskcopilot-alb-sg`** → add inbound **HTTPS 443 from `0.0.0.0/0`**.
3. **EC2 → Load Balancers → `deskcopilot-alb` → Listeners → Add listener**: HTTPS : 443 → forward to `deskcopilot-frontend-tg`. Certificate from ACM: pick yours.
4. Edit the **HTTP : 80** listener: change its action to **Redirect to HTTPS 443**.
5. In your DNS, add a **CNAME** record from `app.yourdomain.com` to the ALB DNS name (in Route 53: an **A record, Alias → Application Load Balancer**).

### Option B: no domain, use CloudFront's free HTTPS address
1. **CloudFront → Create distribution**:
   - Origin: choose the ALB (`deskcopilot-alb...elb.amazonaws.com`). Protocol **HTTP only**, port 80.
   - Under origin settings, set **Response timeout** to **60** seconds. Chat answers can take longer than the 30-second default.
   - Viewer protocol policy: **Redirect HTTP to HTTPS**.
   - Allowed HTTP methods: **GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE** (login and uploads use POST).
   - Cache policy: **CachingDisabled**. Origin request policy: **AllViewer**, which passes the login cookie through.
   - Web Application Firewall (WAF): optional; it adds cost.
2. After it deploys (5 to 15 minutes), open `https://<id>.cloudfront.net`.
3. Lock the ALB so it only accepts traffic from CloudFront: in `deskcopilot-alb-sg`, replace the `0.0.0.0/0` rule on port 80 with source **prefix list `com.amazonaws.global.cloudfront.origin-facing`**.

### Then, for either option: make the cookie secure again
1. **ECS → Task definitions → deskcopilot-frontend → Create new revision**. **Delete** `COOKIE_SECURE`, or set it to `true`. Create.
2. **ECS → deskcopilot → Services → frontend → Update** → choose the new revision → Update.
3. Log in again over `https://`. Over `http://`, login now deliberately fails.

---

## 10. Everyday operations

**Deploy a code change**
1. Rebuild and push the changed image(s), as in step 1.2.
2. **ECS → Services → (service) → Update → tick "Force new deployment" → Update.** ECS starts a new task with the new image and then stops the old one.

**Read logs:** **CloudWatch → Log groups → `/ecs/deskcopilot-backend`** (and the others). Each task writes its own log stream.

**Pause to save money:** set each service's desired tasks to **0**. The load balancer still costs about $20/month and OpenSearch about $35–45/month while they exist; delete them when you're done.

**Set a budget alarm (do this today):** **Billing → Budgets → Create budget → Monthly cost budget** → e.g. $50 → your email address.

**Old access keys:** keep them for local development only. They must never go into ECS. If any keys were ever shared or committed, deactivate them in **IAM → Users → Security credentials**.

---

## 11. Troubleshooting

| What you see | Likely cause | Fix |
|---|---|---|
| Task stops: `CannotPullContainerError` | Public IP off, or wrong image URI | Turn on public IP in the service networking; check the URI and tag in ECR |
| Task stops: `exec format error` | Wrong CPU architecture | Task definition must be **Linux/X86_64** |
| Task stops: `ResourceInitializationError ... secrets/logs` | Task execution role missing | Pick `ecsTaskExecutionRole` in the task definition |
| ALB shows **503** | No healthy frontend task | Check the frontend service's tasks and the target group's **Targets** tab |
| ALB shows **502** or targets *unhealthy* | Port 3000 not reachable from the ALB | `deskcopilot-frontend-sg` must allow 3000 from `deskcopilot-alb-sg` |
| Login page reloads with no error | Secure cookie over `http://` | Use HTTPS, or `COOKIE_SECURE=false` while testing |
| Chat: "Could not reach backend" | Service Connect or firewall | Backend uses "client and server" with port name `backend`; frontend uses "client side only"; `deskcopilot-internal-sg` allows 8000 from `deskcopilot-frontend-sg`; `BACKEND_URL=http://backend:8000`. Service Connect is only added to tasks started **after** it was configured, so force a new deployment of the frontend. |
| File Storage: "Ingestor offline" | Same, for the ingestor | Same checks with port 8002 and `INGESTOR_URL` |
| `403` / `security_exception` from OpenSearch in the logs | Role not allowed by OpenSearch | Step 4: check the domain access policy, then re-run the mapping script with the right ARNs |
| `AccessDeniedException` from Bedrock | Role policy doesn't cover the model | Compare with the working IAM user's Bedrock statement (step 3) |
| `AccessDenied` on S3 or DynamoDB | Wrong bucket, table name or region in the role policy | Fix the inline policy; changes apply within a minute, no redeploy needed |
| Errors mention invalid AWS keys | `AWS_ACCESS_KEY_ID` set in the task definition | Remove both key variables entirely, so the task role is used |

---

## What this setup doesn't do yet (later improvements)

- **Private subnets and a NAT gateway or VPC endpoints:** containers without public IPs.
- **OpenSearch inside the VPC:** the domain is still reachable from the internet, although it's IAM-protected.
- **Secrets Manager** for `ADMIN_PASSWORD` and `AUTH_SECRET`.
- **More than one task per service**, for high availability.
- **WAF rate limiting**, to cap Bedrock spend.
- **CI/CD:** GitHub Actions building and deploying on every push.
- **Infrastructure as code** (CDK or Terraform), so all of this can be recreated with one command.
