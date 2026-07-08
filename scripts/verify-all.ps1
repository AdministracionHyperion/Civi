$ErrorActionPreference = "Stop"
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")

& (Join-Path $PSScriptRoot "verify-service.ps1") -ServicePath "packages/python-common" -SkipTests

Get-ChildItem -LiteralPath (Join-Path $root "services") -Directory | ForEach-Object {
  & (Join-Path $PSScriptRoot "verify-service.ps1") -ServicePath ("services/" + $_.Name) -SkipTests
}

$pythonPathParts = @((Join-Path $root "packages/python-common/src"))
Get-ChildItem -LiteralPath (Join-Path $root "services") -Directory | ForEach-Object {
  $srcPath = Join-Path $_.FullName "src"
  if (Test-Path -LiteralPath $srcPath) {
    $pythonPathParts += $srcPath
  }
}
$env:PYTHONPATH = ($pythonPathParts -join [System.IO.Path]::PathSeparator)

$pytestTargets = @()
$offlineTestsPath = Join-Path $root "tests"
if ((Test-Path -LiteralPath $offlineTestsPath) -and (Get-ChildItem -LiteralPath $offlineTestsPath -Recurse -Filter "*.py" -File -ErrorAction SilentlyContinue)) {
  $pytestTargets += $offlineTestsPath
}
Get-ChildItem -LiteralPath (Join-Path $root "services") -Directory | ForEach-Object {
  $testsPath = Join-Path $_.FullName "tests"
  if ((Test-Path -LiteralPath $testsPath) -and (Get-ChildItem -LiteralPath $testsPath -Recurse -Filter "*.py" -File -ErrorAction SilentlyContinue)) {
    $pytestTargets += $testsPath
  }
}

if ($pytestTargets.Count -gt 0) {
  python -m pytest @pytestTargets -q
  if ($LASTEXITCODE -ne 0) {
    throw "pytest failed for one or more services"
  }
}
