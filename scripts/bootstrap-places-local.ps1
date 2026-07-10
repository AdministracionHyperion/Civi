param(
  [string]$DatabaseUrl = "postgresql+psycopg://civi:civi@localhost:5432/civi",
  [switch]$ViaDocker
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
Set-Location -LiteralPath $root

$catalogRel = "services/places-service/data/raw/places_colombia_original.json"
$santanderRel = "services/places-service/data/geocodes/santander/geocodes_santander_priorizado_validado.csv"
$manizalesRel = "services/places-service/data/geocodes/manizales/geocodes_manizales_validado.csv"
$reportRel = "services/places-service/data/reports"

foreach ($path in @($catalogRel, $santanderRel, $manizalesRel)) {
  if (-not (Test-Path -LiteralPath (Join-Path $root $path))) {
    throw "Missing required data file: $path"
  }
}

New-Item -ItemType Directory -Force -Path (Join-Path $root $reportRel) | Out-Null

if ($ViaDocker) {
  $catalogInput = "/app/service/data/raw/places_colombia_original.json"
  $santanderInput = "/app/service/data/geocodes/santander/geocodes_santander_priorizado_validado.csv"
  $manizalesInput = "/app/service/data/geocodes/manizales/geocodes_manizales_validado.csv"
  $reportDir = "/app/service/data/reports"
  $dbUrl = "postgresql+psycopg://civi:civi@postgres:5432/civi"
  $composeFile = Join-Path $root "infra/docker-compose.local.yml"

  function Invoke-PlacesDocker {
    param([Parameter(Mandatory = $true)][string[]]$Args)
    docker compose -f $composeFile exec -T places-service python -m @Args
    if ($LASTEXITCODE -ne 0) {
      throw "places CLI failed (docker): $($Args -join ' ')"
    }
  }

  Write-Host "1/3 Import national catalog (docker)..."
  Invoke-PlacesDocker -Args @(
    "places_service.cli.import_catalog",
    "--input", $catalogInput,
    "--apply",
    "--skip-geocoding",
    "--database-url", $dbUrl,
    "--report-dir", $reportDir
  )

  Write-Host "2/3 Import Santander validated geocodes (docker)..."
  Invoke-PlacesDocker -Args @(
    "places_service.cli.import_santander_geocodes",
    "--input", $santanderInput,
    "--apply",
    "--database-url", $dbUrl,
    "--report-path", "$reportDir/santander_geocode_import_report.json"
  )

  Write-Host "3/3 Import Manizales validated geocodes (docker)..."
  Invoke-PlacesDocker -Args @(
    "places_service.cli.import_manizales_geocodes",
    "--input", $manizalesInput,
    "--apply",
    "--database-url", $dbUrl,
    "--report-path", "$reportDir/manizales_geocode_import_report.json"
  )
} else {
  $env:PYTHONPATH = @(
    (Join-Path $root "services/places-service/src"),
    (Join-Path $root "packages/python-common/src")
  ) -join ";"
  $env:PLACES_DATABASE_URL = $DatabaseUrl
  $env:PLACES_GEOCODING_MODE = "disabled"

  function Invoke-PlacesHost {
    param([Parameter(Mandatory = $true)][string[]]$Args)
    python -m @Args
    if ($LASTEXITCODE -ne 0) {
      throw "places CLI failed: $($Args -join ' ')"
    }
  }

  Write-Host "1/3 Import national catalog..."
  Invoke-PlacesHost -Args @(
    "places_service.cli.import_catalog",
    "--input", $catalogRel,
    "--apply",
    "--skip-geocoding",
    "--database-url", $DatabaseUrl,
    "--report-dir", $reportRel
  )

  Write-Host "2/3 Import Santander validated geocodes..."
  Invoke-PlacesHost -Args @(
    "places_service.cli.import_santander_geocodes",
    "--input", $santanderRel,
    "--apply",
    "--database-url", $DatabaseUrl,
    "--report-path", "$reportRel/santander_geocode_import_report.json"
  )

  Write-Host "3/3 Import Manizales validated geocodes..."
  Invoke-PlacesHost -Args @(
    "places_service.cli.import_manizales_geocodes",
    "--input", $manizalesRel,
    "--apply",
    "--database-url", $DatabaseUrl,
    "--report-path", "$reportRel/manizales_geocode_import_report.json"
  )
}

Write-Host "Places bootstrap complete."
