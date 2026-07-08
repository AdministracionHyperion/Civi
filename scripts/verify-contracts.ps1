$ErrorActionPreference = "Stop"
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$eventsPath = Join-Path $root "contracts/events.asyncapi.yaml"

if (-not (Test-Path -LiteralPath $eventsPath)) {
  throw "Missing contracts/events.asyncapi.yaml"
}

$content = Get-Content -LiteralPath $eventsPath -Raw
if ($content -notmatch "(?m)^asyncapi:\s*3\.0\.0\s*$") {
  throw "events.asyncapi.yaml must use AsyncAPI 3.0.0"
}

$requiredChannels = @(
  "message.received",
  "conversation.completed",
  "consent.updated",
  "appointment.created",
  "appointment.cancelled",
  "reminder.scheduled",
  "reminder.due",
  "notification.queued",
  "notification.sent"
)

foreach ($channel in $requiredChannels) {
  $escaped = [regex]::Escape($channel)
  $channelPattern = "(?m)^\s{{2}}{0}:\s*$" -f $escaped
  if ($content -notmatch $channelPattern) {
    throw "Missing AsyncAPI channel: $channel"
  }
  if ($content -notmatch "#/channels/$escaped") {
    throw "Missing AsyncAPI operation reference for channel: $channel"
  }
  if ($content -notmatch "const:\s*$escaped") {
    throw "Missing AsyncAPI event_type const for channel: $channel"
  }
}

$openapiFiles = Get-ChildItem -LiteralPath (Join-Path $root "contracts") -Filter "*.openapi.yaml"
$methods = @("get", "post", "put", "patch", "delete")
$methodPattern = ($methods | ForEach-Object { [regex]::Escape($_) }) -join "|"

foreach ($file in $openapiFiles) {
  $lines = Get-Content -LiteralPath $file.FullName
  $openapiContent = $lines -join "`n"
  if ($openapiContent -notmatch "(?m)^openapi:\s*3\.1\.0\s*$") {
    throw "$($file.Name) must use OpenAPI 3.1.0"
  }

  for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -notmatch "^  (/internal/[^:]+):\s*$") {
      continue
    }
    $path = $matches[1]
    $pathEnd = $lines.Count
    for ($j = $i + 1; $j -lt $lines.Count; $j++) {
      if ($lines[$j] -match "^  /[^:]+:\s*$") {
        $pathEnd = $j
        break
      }
    }

    $cursor = $i + 1
    while ($cursor -lt $pathEnd) {
      if ($lines[$cursor] -notmatch "^\s{4}($methodPattern):\s*$") {
        $cursor++
        continue
      }
      $method = $matches[1]
      $methodEnd = $pathEnd
      for ($k = $cursor + 1; $k -lt $pathEnd; $k++) {
        if ($lines[$k] -match "^\s{4}($methodPattern):\s*$") {
          $methodEnd = $k
          break
        }
      }
      $methodBlock = ($lines[($cursor + 1)..($methodEnd - 1)] -join "`n")
      if ($methodBlock -notmatch "(?m)^\s{6}security:\s*$") {
        throw "$($file.Name) $method $path must declare security"
      }
      $cursor = $methodEnd
    }
  }
}

Write-Host "Civi contract verification passed."
