# Plan B — AWS deploy (awaiting approval)

**Status:** Phase 1 **applied** (no hosted API).  
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
| DynamoDB `thyme-recipes` | Standardized recipe JSON (next sprint) |
| S3 + CloudFront | Host React build (`*.cloudfront.net`, no custom domain) |
| SSM SecureString | Fernet key for encrypting BYOK payloads |

**Not in first apply (on purpose):** Lambda/App Runner API packaging, Bedrock, RDS, OpenSearch, Route 53, NAT gateways.

API can keep running on a teammate laptop / later Lambda once you approve a second step.

## Estimated cost (class + family scale)

Assumptions: ~6–20 users, light demos, little always-on traffic, **BYOK so frontier tokens are billed to each user**.

| Item | Estimate / month |
|------|------------------|
| Cognito | **$0** (free tier ≫ class MAUs) |
| DynamoDB on-demand | **~$0–1** |
| S3 storage + requests | **~$0–1** |
| CloudFront (PriceClass_100) | **~$0–3** (near $0 if rarely hit) |
| SSM | **~$0** |
| **AWS infra subtotal** | **~$0–5** typical |
| Ollama on laptops | **$0** |
| OpenAI/Anthropic via BYOK | **Paid by each user** (not the AWS account) |
| Optional later: always-on API (App Runner) | **+$7–15** if you add it |
| Optional later: Lambda API | usually **$0–2** at this scale |

**Recommended budget to expect:** about **$5/month** AWS for the static+auth+DynamoDB stack, plus whatever individuals spend on their own API keys. Avoid App Runner until you need a public API URL 24/7.

## Apply steps (only after you say yes)

```powershell
cd infra
copy terraform.tfvars.example terraform.tfvars
terraform init
terraform plan    # review together
terraform apply   # only when approved
```

Then:

1. `cd frontend && npm run build`
2. `aws s3 sync dist/ s3://$(terraform output -raw frontend_bucket)`
3. Open `terraform output -raw cloudfront_url`
4. Wire Cognito client id into the web app + finish JWT verification in `shared/auth.py`
5. Decide API host (keep local vs Lambda) in a follow-up

## Destroy (if you want it gone)

```powershell
cd infra
terraform destroy
```
