$ErrorActionPreference = "Stop"
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$allowedLocalEnvFiles = @(
  (Join-Path $root.Path ".env"),
  (Join-Path $root.Path ".env.deploy")
)

$forbidden = Get-ChildItem -LiteralPath $root -Recurse -Force -File | Where-Object {
  (($_.Name -eq ".env" -or $_.Name -eq ".env.deploy") -and ($allowedLocalEnvFiles -notcontains $_.FullName)) -or
  $_.Name -like "*.log" -or
  $_.Name -eq "cloudflared.exe" -or
  $_.Name -eq "URL_PUBLICA.txt" -or
  $_.Name -like "prod_*.txt" -or
  $_.FullName -match "\\node_modules\\" -or
  $_.FullName -match "\\.venv" -or
  $_.FullName -match "\\scratch\\" -or
  $_.FullName -match "\\backups\\"
}

if ($forbidden) {
  $forbidden | Select-Object FullName | Format-Table -AutoSize
  throw "Forbidden operational artifacts found in restructured workspace."
}

$requiredDocs = @(
  "README.md",
  "docs/architecture-microservices.md",
  "docs/cutover-checklist.md",
  "docs/security-baseline.md",
  "docs/bot-orchestrator-flow.md",
  "docs/operational-handoff.md",
  "docs/deployment.md",
  "docs/product-parity.md",
  "docs/clean-product-blueprint.md"
)
foreach ($requiredDoc in $requiredDocs) {
  $docPath = Join-Path $root $requiredDoc
  if (-not (Test-Path -LiteralPath $docPath)) {
    throw "Missing required restructuring document: $requiredDoc"
  }
}

$activeRoots = @(
  (Join-Path $root "services"),
  (Join-Path $root "packages")
)
$retiredReferencePatterns = @(
  ("packages/" + "leg" + "acy-bot"),
  ("packages\" + "leg" + "acy-bot"),
  ("migration-" + "reference"),
  ("src_" + "leg" + "acy_import"),
  ("leg" + "acy_bridge"),
  "from src.",
  "import src."
)
$retiredRefs = @()
foreach ($activeRoot in $activeRoots) {
  if (Test-Path -LiteralPath $activeRoot) {
    $retiredRefs += Get-ChildItem -LiteralPath $activeRoot -Recurse -Force -File |
      Select-String -Pattern $retiredReferencePatterns -SimpleMatch -ErrorAction SilentlyContinue
  }
}
if ($retiredRefs) {
  $retiredRefs | Select-Object Path, LineNumber, Line | Format-Table -AutoSize
  throw "Active services/packages must not import or reference retired implementation code."
}

& (Join-Path $PSScriptRoot "verify-secrets.ps1")

& (Join-Path $PSScriptRoot "verify-node-audit.ps1")

python (Join-Path $PSScriptRoot "verify-config-defaults.py")
if ($LASTEXITCODE -ne 0) {
  throw "Configuration default verification failed."
}

& (Join-Path $PSScriptRoot "verify-deploy-config.ps1") -EnvFile (Join-Path $root ".env.deploy.example") -AllowPlaceholders

python (Join-Path $PSScriptRoot "verify-service-boundaries.py")
if ($LASTEXITCODE -ne 0) {
  throw "Service boundary verification failed."
}

python (Join-Path $PSScriptRoot "verify-data-ownership.py")
if ($LASTEXITCODE -ne 0) {
  throw "Data ownership verification failed."
}

python -m compileall -q (Join-Path $root "packages/python-common/src")
if ($LASTEXITCODE -ne 0) {
  throw "Python common compile failed."
}

& (Join-Path $PSScriptRoot "verify-contracts.ps1")

python (Join-Path $PSScriptRoot "verify-runtime-contracts.py")
if ($LASTEXITCODE -ne 0) {
  throw "Runtime/OpenAPI route verification failed."
}

& (Join-Path $PSScriptRoot "verify-all.ps1")

Write-Host "Civi restructured workspace verification passed."
