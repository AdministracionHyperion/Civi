param(
  [string]$EnvFile = (Join-Path (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")) ".env"),
  [switch]$AllowPlaceholders
)

$ErrorActionPreference = "Stop"
$argsList = @(
  (Join-Path $PSScriptRoot "verify-deploy-config.py"),
  "--env-file",
  $EnvFile
)
if ($AllowPlaceholders) {
  $argsList += "--allow-placeholders"
}

python @argsList
if ($LASTEXITCODE -ne 0) {
  throw "Deploy configuration verification failed."
}
