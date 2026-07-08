param(
  [Parameter(Mandatory=$true)]
  [string]$ServicePath,
  [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$service = Resolve-Path -LiteralPath (Join-Path $root $ServicePath)

if ($service.Path -notlike "$($root.Path)*") {
  throw "Service path is outside workspace: $($service.Path)"
}

if (Test-Path -LiteralPath (Join-Path $service "pyproject.toml")) {
  $srcPath = Join-Path $service "src"
  if (-not (Test-Path -LiteralPath $srcPath)) {
    throw "Python service has pyproject.toml but no src directory: $ServicePath"
  }

  python -m compileall -q $srcPath
  if ($LASTEXITCODE -ne 0) {
    throw "Python compile failed for $ServicePath"
  }

  $testsPath = Join-Path $service "tests"
  $hasPythonTests = (Test-Path -LiteralPath $testsPath) -and
    (Get-ChildItem -LiteralPath $testsPath -Recurse -Filter "*.py" -File -ErrorAction SilentlyContinue)
  if ($hasPythonTests -and -not $SkipTests) {
    $pythonPathParts = @((Join-Path $root "packages/python-common/src"))
    Get-ChildItem -LiteralPath (Join-Path $root "services") -Directory | ForEach-Object {
      $candidateSrc = Join-Path $_.FullName "src"
      if (Test-Path -LiteralPath $candidateSrc) {
        $pythonPathParts += $candidateSrc
      }
    }
    $previousPythonPath = $env:PYTHONPATH
    $env:PYTHONPATH = ($pythonPathParts -join [System.IO.Path]::PathSeparator)
    try {
      python -m pytest $testsPath -q
      if ($LASTEXITCODE -ne 0) {
        throw "pytest failed for $ServicePath"
      }
    } finally {
      $env:PYTHONPATH = $previousPythonPath
    }
  }
}

if (Test-Path -LiteralPath (Join-Path $service "package.json")) {
  Push-Location $service
  try {
    npm run check
    if ($LASTEXITCODE -ne 0) {
      throw "npm check failed for $ServicePath"
    }
  } finally {
    Pop-Location
  }
}
