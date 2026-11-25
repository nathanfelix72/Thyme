# Deploy / update the Thyme API on EC2 (Docker Compose over SSH).
#
# Prerequisites:
#   - terraform apply already created the EC2 API + wrote infra/thyme-api.pem
#   - AWS CLI credentials that can read SSM
#   - optional: npm run sync:secrets  (uploads TAVILY/etc from local .env to SSM)
#
# Usage (repo root):
#   .\scripts\deploy-api.ps1
#   .\scripts\deploy-api.ps1 -EnvOnly   # refresh .env from SSM + recreate container (no image rebuild)
#   npm run deploy:api

param(
  [switch]$EnvOnly
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$infraDir = Join-Path $repoRoot "infra"
$deployDir = Join-Path $repoRoot "deploy"
$pem = Join-Path $infraDir "thyme-api.pem"

# SSM path suffix -> env var name (everything under /thyme/)
# Shared host secrets only. Per-user OpenAI/Anthropic/Tavily live in DynamoDB via AI settings.
$ssmToEnv = @{
  "thyme_secrets_key"    = "THYME_SECRETS_KEY"
  "hf_token"             = "HF_TOKEN"
  "google_client_id"     = "GOOGLE_CLIENT_ID"
  "google_client_secret" = "GOOGLE_CLIENT_SECRET"
  "langsmith_api_key"    = "LANGSMITH_API_KEY"
}

function Invoke-Ssh([string]$HostSpec, [string]$RemoteCmd) {
  $prev = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  & ssh -i $pem -o StrictHostKeyChecking=accept-new $HostSpec $RemoteCmd
  $code = $LASTEXITCODE
  $ErrorActionPreference = $prev
  if ($code -ne 0) { throw "ssh failed ($code): $HostSpec $RemoteCmd" }
}

function Invoke-Scp([string[]]$Sources, [string]$Dest) {
  $prev = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  & scp -i $pem -o StrictHostKeyChecking=accept-new @Sources $Dest
  $code = $LASTEXITCODE
  $ErrorActionPreference = $prev
  if ($code -ne 0) { throw "scp failed ($code) -> $Dest" }
}

function Get-SsmThymeSecrets([string]$Region) {
  $map = @{}
  $raw = aws ssm get-parameters-by-path `
    --path "/thyme" `
    --recursive `
    --with-decryption `
    --region $Region `
    --output json 2>$null
  if ($LASTEXITCODE -ne 0 -or -not $raw) {
    throw "Failed to list SSM parameters under /thyme (check IAM + aws login)."
  }
  $parsed = $raw | ConvertFrom-Json
  foreach ($p in $parsed.Parameters) {
    $leaf = ($p.Name -split "/")[-1]
    if ($ssmToEnv.ContainsKey($leaf)) {
      $map[$ssmToEnv[$leaf]] = [string]$p.Value
    }
  }
  return $map
}

if (-not (Test-Path $pem)) {
  throw "Missing $pem - run terraform apply in infra/ first."
}

# OpenSSH on Windows rejects keys that are readable by other local users.
icacls $pem /inheritance:r | Out-Null
icacls $pem /grant:r "${env:USERNAME}:(R)" | Out-Null

Push-Location $infraDir
try {
  $ip = terraform output -raw ec2_api_ip
  $region = terraform output -raw aws_region
  $cfUrl = terraform output -raw cloudfront_url
} finally {
  Pop-Location
}

if (-not $ip) { throw "ec2_api_ip is empty - enable_ec2_api and apply." }

Write-Host "Fetching /thyme/* secrets from SSM..."
$secrets = Get-SsmThymeSecrets $region
$fernet = $secrets["THYME_SECRETS_KEY"]
if (-not $fernet) {
  throw "Missing /thyme/thyme_secrets_key in SSM (created by terraform)."
}

$envPath = Join-Path $deployDir ".env"
# Base config + any secrets present in SSM. No AWS access keys (instance role).
$lines = @(
  "THYME_ENV=aws",
  "THYME_ALLOW_ANON=false",
  "AWS_REGION=$region",
  "AWS_DEFAULT_REGION=$region",
  "USER_SECRETS_TABLE=thyme-user-secrets",
  "RECIPES_TABLE=thyme-recipes",
  "COGNITO_USER_POOL_ID=us-west-1_Oqxx0Qvpk",
  "COGNITO_APP_CLIENT_ID=3aj94humt4rjn2gu9uklv9sd5j",
  "THYME_SECRETS_KEY=$fernet",
  "CHROMA_DIR=/data/chroma",
  "FRONTEND_ORIGIN=$cfUrl"
)
foreach ($k in @(
    "HF_TOKEN", "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "LANGSMITH_API_KEY"
  )) {
  if ($secrets.ContainsKey($k) -and $secrets[$k]) {
    $lines += "$k=$($secrets[$k])"
    Write-Host "  + $k"
  } else {
    Write-Host "  - $k (optional shared; npm run sync:secrets)"
  }
}
Write-Host "  (BYOK OpenAI/Anthropic/Tavily: AI settings per Cognito user)"
[System.IO.File]::WriteAllText($envPath, (($lines -join "`n") + "`n"))

Write-Host "Waiting for SSH on ubuntu@${ip} ..."
$deadline = (Get-Date).AddMinutes(5)
$sshReady = $false
while ((Get-Date) -lt $deadline) {
  $prev = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  ssh -i $pem -o StrictHostKeyChecking=accept-new -o ConnectTimeout=5 -o BatchMode=yes `
    "ubuntu@${ip}" "echo ok" 2>$null | Out-Null
  $code = $LASTEXITCODE
  $ErrorActionPreference = $prev
  if ($code -eq 0) { $sshReady = $true; break }
  Start-Sleep -Seconds 5
}
if (-not $sshReady) {
  throw "SSH not ready on $ip - is user_data / Docker still installing? Retry in a minute."
}

$hostSpec = "ubuntu@${ip}"
# Server layout is /opt/thyme/{docker-compose.yml,backend/,.env} so context must be ./backend
$composeSrc = Join-Path $deployDir "docker-compose.yml"
$composeServer = Join-Path $env:TEMP "thyme-docker-compose.server.yml"
$composeText = [System.IO.File]::ReadAllText($composeSrc) -replace "context:\s*\.\./backend", "context: ./backend"
[System.IO.File]::WriteAllText($composeServer, ($composeText -replace "`r`n", "`n"))

Write-Host "Syncing config to ${hostSpec}:/opt/thyme ..."
Invoke-Ssh $hostSpec "mkdir -p /opt/thyme/backend/app"
$prev = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& scp -i $pem -o StrictHostKeyChecking=accept-new $envPath "${hostSpec}:/opt/thyme/.env"
if ($LASTEXITCODE -ne 0) { throw "scp .env failed" }
& scp -i $pem -o StrictHostKeyChecking=accept-new $composeServer "${hostSpec}:/opt/thyme/docker-compose.yml"
if ($LASTEXITCODE -ne 0) { throw "scp docker-compose.yml failed" }
$ErrorActionPreference = $prev

if ($EnvOnly) {
  Write-Host "Recreating container with new env (no image rebuild)..."
  Invoke-Ssh $hostSpec "cd /opt/thyme && sudo docker compose up -d --force-recreate --no-build"
} else {
  Invoke-Scp @((Join-Path $deployDir "remote-up.sh")) "${hostSpec}:/opt/thyme/"

  Write-Host "Syncing backend/ for image build..."
  Invoke-Scp @(
    (Join-Path $repoRoot "backend\Dockerfile"),
    (Join-Path $repoRoot "backend\.dockerignore"),
    (Join-Path $repoRoot "backend\requirements.txt")
  ) "${hostSpec}:/opt/thyme/backend/"

  $ErrorActionPreference = "Continue"
  & scp -i $pem -o StrictHostKeyChecking=accept-new -r `
    (Join-Path $repoRoot "backend\app") `
    "${hostSpec}:/opt/thyme/backend/"
  if ($LASTEXITCODE -ne 0) { throw "scp of backend/app failed" }
  $ErrorActionPreference = $prev

  Write-Host "Building and starting containers (first build can take several minutes)..."
  Invoke-Ssh $hostSpec "bash /opt/thyme/remote-up.sh"
}

Write-Host ""
Write-Host "Direct health:  http://${ip}:8765/api/health"
Write-Host "Via CloudFront: $cfUrl/api/health"
Write-Host "Done."
