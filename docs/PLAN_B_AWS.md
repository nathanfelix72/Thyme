# Plan B — AWS deploy

**Status:** Phase 1 applied + **EC2 API** (always-on, BYOK).  
**Account:** `248189945218` (`nathan-cli`) · region `us-west-1`

| Output | Value |
|--------|--------|
| CloudFront | https://dv5md9hmzm76i.cloudfront.net |
| S3 bucket | `thyme-web-110c07cf` |
| Cognito pool | `us-west-1_Oqxx0Qvpk` |
| Cognito client | `3aj94humt4rjn2gu9uklv9sd5j` |
| Secrets table | `thyme-user-secrets` |
| Recipes table | `thyme-recipes` |
| Fernet SSM | `/thyme/thyme_secrets_key` |
| EC2 API | `t3.small` (~$12–15/mo) → CloudFront `/api/*` |

Note: **Lightsail is not available in `us-west-1`**, so production API is EC2 in the same region as Cognito/DynamoDB.

## What Plan A already did (no AWS cost)

- Local default: **Ollama `qwen2.5:7b`**
- Settings UI + API for **BYOK** (OpenAI / Anthropic keys encrypted on disk)
- Provider test chat at `POST /api/settings/test-chat`
- Terraform files ready; nothing created in AWS yet

## What Plan B would create (cheap stack)

| Resource | Purpose |
|----------|---------|
| Cognito user pool + app client | Email/password accounts |
| DynamoDB `thyme-user-secrets` | Encrypted BYOK keys per user |
| DynamoDB `thyme-recipes` | Standardized recipe JSON (LLM Phase 1 RAG) |
| S3 + CloudFront | Host React build (`*.cloudfront.net`, no custom domain) |
| SSM SecureString | Fernet key for encrypting BYOK payloads |

**Hosted API:** EC2 Ubuntu + Docker (`deploy/`), CloudFront origin for `/api/*`. Production AI is **BYOK only** (no Ollama on the box). Local laptops still use Ollama.

## Estimated cost (class + family scale)

Assumptions: ~6–20 users, light demos, **BYOK so frontier tokens are billed to each user**.

| Item | Estimate / month |
|------|------------------|
| Cognito | **$0** (free tier ≫ class MAUs) |
| DynamoDB on-demand | **~$0–1** |
| S3 storage + requests | **~$0–1** |
| CloudFront (PriceClass_100) | **~$0–3** |
| SSM | **$0** |
| EC2 API (`t3.small` + 30 GB gp3 + EIP) | **~$12–15** |
| **AWS total** | **~$12–20** typical |
| Ollama on laptops | **$0** |
| OpenAI/Anthropic via BYOK | **Paid by each user** (not the AWS account) |

## Apply / update

```powershell
cd infra
copy terraform.tfvars.example terraform.tfvars   # once
terraform init
terraform apply
cd ..
.\scripts\deploy-api.ps1
```

Health: `https://dv5md9hmzm76i.cloudfront.net/api/health` should show `"env":"aws"`.

## Destroy (if you want it gone)

```powershell
cd infra
terraform destroy
```
