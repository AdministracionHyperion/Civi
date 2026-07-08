$ErrorActionPreference = "Stop"
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")

$nodeManifests = Get-ChildItem -LiteralPath (Join-Path $root "services") -Recurse -Force -File -Filter "package.json"
foreach ($manifest in $nodeManifests) {
  Push-Location $manifest.DirectoryName
  try {
    npm audit --omit=dev --audit-level=moderate --package-lock-only
    if ($LASTEXITCODE -ne 0) {
      throw "Node production dependency audit failed for $($manifest.DirectoryName)."
    }
  } finally {
    Pop-Location
  }
}

Write-Host "Civi Node production dependency audit passed."
