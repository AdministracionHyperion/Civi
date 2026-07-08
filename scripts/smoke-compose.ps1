param(
  [int]$StartupSeconds = 10,
  [int]$HealthTimeoutSeconds = 180,
  [string]$EnvFile = ""
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$composeFile = Join-Path $root "infra/docker-compose.local.yml"
$composeArgs = @()
$resolvedEnvFile = $null
if ($EnvFile) {
  $resolvedEnvFile = Resolve-Path -LiteralPath $EnvFile
  $composeArgs += @("--env-file", $resolvedEnvFile.Path)
}
$composeArgs += @("-f", $composeFile)

function Get-EnvFileValue {
  param(
    [string]$Key,
    [string]$DefaultValue
  )

  if (-not $resolvedEnvFile) {
    return $DefaultValue
  }
  $match = Get-Content -LiteralPath $resolvedEnvFile.Path |
    Where-Object { $_ -match "^\s*$([regex]::Escape($Key))\s*=" } |
    Select-Object -First 1
  if (-not $match) {
    return $DefaultValue
  }
  $value = (($match -split "=", 2)[1]).Trim().Trim('"').Trim("'")
  if ([string]::IsNullOrWhiteSpace($value)) {
    return $DefaultValue
  }
  return $value
}

function Wait-HealthUrl {
  param(
    [string]$Url,
    [int]$TimeoutSeconds
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $lastError = ""
  while ((Get-Date) -lt $deadline) {
    try {
      $response = Invoke-RestMethod -Method Get -Uri $Url -TimeoutSec 5
      if ($response.status -eq "ok") {
        Write-Host "Health ok: $Url"
        return
      }
      $lastError = "unexpected status '$($response.status)'"
    } catch {
      $lastError = $_.Exception.Message
    }
    Start-Sleep -Seconds 2
  }

  Write-Host "Docker compose status before health failure:"
  docker compose @script:composeArgs ps
  throw "Health check failed for $Url after $TimeoutSeconds seconds. Last error: $lastError"
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
  throw "Docker daemon is not available. Start Docker Desktop and rerun this script."
}

$started = $false
try {
  docker compose @composeArgs up -d --build
  if ($LASTEXITCODE -ne 0) {
    throw "docker compose up failed"
  }
  $started = $true

  Start-Sleep -Seconds $StartupSeconds

  $channelGatewayPort = Get-EnvFileValue -Key "CHANNEL_GATEWAY_PORT" -DefaultValue "8080"
  $adminServicePort = Get-EnvFileValue -Key "ADMIN_SERVICE_PORT" -DefaultValue "8089"

  $healthUrls = @(
    "http://127.0.0.1:$channelGatewayPort/health/live",
    "http://127.0.0.1:8081/health/live",
    "http://127.0.0.1:8082/health/live",
    "http://127.0.0.1:8083/health/live",
    "http://127.0.0.1:8084/health/live",
    "http://127.0.0.1:8085/health/live",
    "http://127.0.0.1:8086/health/live",
    "http://127.0.0.1:8087/health/live",
    "http://127.0.0.1:8088/health/live",
    "http://127.0.0.1:$adminServicePort/health/live",
    "http://127.0.0.1:8090/health/live",
    "http://127.0.0.1:8091/health/live",
    "http://127.0.0.1:8092/health/live",
    "http://127.0.0.1:8093/health/live",
    "http://127.0.0.1:8094/health/live"
  )

  foreach ($url in $healthUrls) {
    Wait-HealthUrl -Url $url -TimeoutSeconds $HealthTimeoutSeconds
  }

  $runningServices = docker compose @composeArgs ps --services --filter "status=running"
  if ($LASTEXITCODE -ne 0) {
    throw "docker compose ps failed"
  }
  if ($runningServices -notcontains "notification-worker") {
    throw "notification-worker is not running"
  }
  if ($runningServices -notcontains "admin-event-audit-worker") {
    throw "admin-event-audit-worker is not running"
  }

  Write-Host "Civi compose smoke passed."
} finally {
  if ($started) {
    docker compose @composeArgs down
  }
}
