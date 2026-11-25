# Push shared infra secrets from local .env into AWS SSM SecureString (/thyme/...).
# Per-user AI / Tavily keys belong in AI settings (DynamoDB), not here.
#
# Usage (repo root):
#   .\scripts\sync-secrets-to-ssm.ps1
#   npm run sync:secrets

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$envFile = Join-Path $repoRoot ".env"
$region = "us-west-1"

# Shared host secrets only (not BYOK). Local .env key -> SSM path.
$secretMap = [ordered]@{
  "HF_TOKEN"             = "/thyme/hf_token"
  "GOOGLE_CLIENT_ID"     = "/thyme/google_client_id"
  "GOOGLE_CLIENT_SECRET" = "/thyme/google_client_secret"
  "LANGSMITH_API_KEY"    = "/thyme/langsmith_api_key"
}

if (-not (Test-Path $envFile)) {
  throw "Missing $envFile - copy .env.example and fill secrets first."
}

function Read-DotEnv([string]$Path) {
  $map = @{}
  foreach ($line in Get-Content $Path) {
    $trim = $line.Trim()
    if (-not $trim -or $trim.StartsWith("#")) { continue }
    $eq = $trim.IndexOf("=")
    if ($eq -lt 1) { continue }
    $key = $trim.Substring(0, $eq).Trim()
    $val = $trim.Substring($eq + 1).Trim()
    if (
      ($val.StartsWith('"') -and $val.EndsWith('"')) -or
      ($val.StartsWith("'") -and $val.EndsWith("'"))
    ) {
      $val = $val.Substring(1, $val.Length - 2)
    }
    $map[$key] = $val
  }
  return $map
}

$dotenv = Read-DotEnv $envFile
$uploaded = 0
$skipped = 0

foreach ($key in $secretMap.Keys) {
  $param = $secretMap[$key]
  $val = $dotenv[$key]
  if (-not $val) {
    Write-Host "skip  $key (empty / missing in .env)"
    $skipped++
    continue
  }

  Write-Host "put   $key -> $param"
  $payload = @{
    Name      = $param
    Type      = "SecureString"
    Value     = $val
    Overwrite = $true
  } | ConvertTo-Json -Compress
  $tmp = Join-Path $env:TEMP "thyme-ssm-$key.json"
  try {
    [System.IO.File]::WriteAllText($tmp, $payload)
    aws ssm put-parameter --cli-input-json "file://$tmp" --region $region | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "ssm put-parameter failed for $param" }
    $uploaded++
  } finally {
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
  }
}

Write-Host ""
Write-Host "Uploaded $uploaded shared secret(s), skipped $skipped."
Write-Host "OpenAI / Anthropic / Tavily: set per user in AI settings (not SSM)."
Write-Host "Next: npm run deploy:api:env  (if HF/Google/LangSmith changed)"
