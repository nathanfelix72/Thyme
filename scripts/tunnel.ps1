# Expose local Thyme API (127.0.0.1:8765) via Cloudflare quick tunnel and
# point the CloudFront site at it by uploading api-config.json (no full rebuild).
#
# Usage (repo root, API already running via `npm start`):
#   npm run tunnel
#   .\scripts\tunnel.ps1
#   .\scripts\tunnel.ps1 -SkipPublish   # print URL only, don't touch S3

param(
  [switch]$SkipPublish,
  [string]$ApiHost = "127.0.0.1",
  [int]$ApiPort = 8765,
  [string]$S3Bucket = "thyme-web-110c07cf",
  [string]$CloudFrontDistributionId = "E2K9WV7B9TSU22"
)

$ErrorActionPreference = "Stop"

function Find-Cloudflared {
  $candidates = @(
    "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe",
    "$env:ProgramFiles\cloudflared\cloudflared.exe"
  )
  foreach ($p in $candidates) {
    if (Test-Path $p) { return $p }
  }
  $cmd = Get-Command cloudflared -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  throw "cloudflared not found. Install: winget install Cloudflare.cloudflared"
}

function Test-ApiHealth {
  try {
    $r = Invoke-WebRequest -Uri "http://${ApiHost}:${ApiPort}/api/health" -UseBasicParsing -TimeoutSec 5
    return $r.StatusCode -eq 200
  } catch {
    return $false
  }
}

function Publish-ApiConfig([string]$ApiBase) {
  $tmp = Join-Path $env:TEMP "thyme-api-config.json"
  $json = (@{ apiBase = $ApiBase } | ConvertTo-Json -Compress) + "`n"
  [System.IO.File]::WriteAllText($tmp, $json)
  Write-Host "Uploading api-config.json -> s3://$S3Bucket/api-config.json"
  aws s3 cp $tmp "s3://$S3Bucket/api-config.json" `
    --content-type "application/json" `
    --cache-control "no-cache, max-age=0"
  if ($LASTEXITCODE -ne 0) { throw "aws s3 cp failed (exit $LASTEXITCODE). Is AWS CLI logged in?" }
  Write-Host "Invalidating CloudFront /api-config.json"
  aws cloudfront create-invalidation `
    --distribution-id $CloudFrontDistributionId `
    --paths "/api-config.json" | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "cloudfront invalidation failed (exit $LASTEXITCODE)" }
}

function Clear-ApiConfig {
  if ($SkipPublish) { return }
  try {
    Publish-ApiConfig ""
    Write-Host "Cleared production apiBase (tunnel stopped)."
  } catch {
    Write-Warning "Could not clear api-config.json on S3: $_"
  }
}

function Get-TunnelUrlFromLogs([string]$OutLog, [string]$ErrLog) {
  $text = ""
  if (Test-Path $OutLog) {
    $text += Get-Content $OutLog -Raw -ErrorAction SilentlyContinue
  }
  if (Test-Path $ErrLog) {
    $text += Get-Content $ErrLog -Raw -ErrorAction SilentlyContinue
  }
  if ($text -match "https://[a-zA-Z0-9.-]+\.trycloudflare\.com") {
    return $Matches[0].TrimEnd("/")
  }
  return $null
}

$cloudflared = Find-Cloudflared
$target = "http://${ApiHost}:${ApiPort}"

if (-not (Test-ApiHealth)) {
  Write-Host "API not reachable at $target/api/health"
  Write-Host "Start it first in another terminal:  npm start"
  exit 1
}

$outLog = Join-Path $env:TEMP "thyme-cloudflared.out.log"
$errLog = Join-Path $env:TEMP "thyme-cloudflared.err.log"
Remove-Item $outLog, $errLog -ErrorAction SilentlyContinue

Write-Host "API OK. Starting Cloudflare quick tunnel -> $target"
Write-Host "Leave this window open while people use the CloudFront site."
Write-Host ""

$proc = Start-Process -FilePath $cloudflared `
  -ArgumentList @("tunnel", "--url", $target, "--no-autoupdate") `
  -RedirectStandardOutput $outLog `
  -RedirectStandardError $errLog `
  -PassThru `
  -NoNewWindow

$published = $false
$tunnelUrl = $null

try {
  $deadline = (Get-Date).AddSeconds(60)
  while (-not $tunnelUrl -and -not $proc.HasExited -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 400
    $tunnelUrl = Get-TunnelUrlFromLogs $outLog $errLog
  }

  if (-not $tunnelUrl) {
    Write-Host "--- cloudflared stdout ---"
    if (Test-Path $outLog) { Get-Content $outLog }
    Write-Host "--- cloudflared stderr ---"
    if (Test-Path $errLog) { Get-Content $errLog }
    throw "Timed out waiting for trycloudflare.com URL from cloudflared."
  }

  Write-Host "Tunnel URL: $tunnelUrl"
  Write-Host "Health:     $tunnelUrl/api/health"
  Write-Host ""

  if (-not $SkipPublish) {
    Publish-ApiConfig $tunnelUrl
    $published = $true
    Write-Host "CloudFront will use this API base after the invalidation finishes (~10-60s)."
    Write-Host "Site: https://dv5md9hmzm76i.cloudfront.net"
  } else {
    Write-Host "SkipPublish set - update api-config manually if needed."
  }

  Write-Host ""
  Write-Host "Press Ctrl+C to stop the tunnel."
  Wait-Process -Id $proc.Id
} finally {
  if (-not $proc.HasExited) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    try { Wait-Process -Id $proc.Id -Timeout 5 } catch { }
  }
  if ($published) { Clear-ApiConfig }
}
