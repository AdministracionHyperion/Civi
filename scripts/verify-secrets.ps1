$ErrorActionPreference = "Stop"
$root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$allowedLocalEnvFiles = @(
  (Join-Path $root.Path ".env"),
  (Join-Path $root.Path ".env.deploy")
)

$secretPatterns = @(
  @{
    Name = "OpenAI-style API key"
    Pattern = "sk-[A-Za-z0-9_-]{20,}"
  },
  @{
    Name = "GitHub token"
    Pattern = "gh[pousr]_[A-Za-z0-9_]{20,}"
  },
  @{
    Name = "Slack token"
    Pattern = "xox[baprs]-[A-Za-z0-9-]{20,}"
  },
  @{
    Name = "AWS access key id"
    Pattern = "AKIA[0-9A-Z]{16}"
  },
  @{
    Name = "Google API key"
    Pattern = "AIza[0-9A-Za-z_-]{35}"
  },
  @{
    Name = "Private key block"
    Pattern = "-----BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----"
  }
)

$files = Get-ChildItem -LiteralPath $root -Recurse -Force -File | Where-Object {
  $_.FullName -notmatch "\\__pycache__\\" -and
  $_.FullName -notmatch "\\.pytest_cache\\" -and
  ($allowedLocalEnvFiles -notcontains $_.FullName)
}

$findings = @()
foreach ($pattern in $secretPatterns) {
  $matches = $files | Select-String -Pattern $pattern.Pattern -ErrorAction SilentlyContinue
  foreach ($match in $matches) {
    $findings += [pscustomobject]@{
      Type = $pattern.Name
      Path = $match.Path
      LineNumber = $match.LineNumber
    }
  }
}

if ($findings) {
  $findings | Format-Table -AutoSize
  throw "Potential real secrets found in restructured workspace."
}

Write-Host "Civi secret scan passed."
