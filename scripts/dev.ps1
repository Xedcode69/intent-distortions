$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
& uv run --locked python scripts/dev.py
exit $LASTEXITCODE
