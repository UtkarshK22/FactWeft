<#
.SYNOPSIS
  Windows wrapper for the Makefile targets (for machines without GNU make).
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/make.ps1 dev
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('image', 'up', 'down', 'seed', 'dev', 'test', 'test-restart', 'lint', 'fmt', 'health', 'logs', 'ps', 'clean')]
    [string]$Target
)

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)

function Invoke-Image {
    docker buildx build ./backend -t factweft-api:latest --load
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

switch ($Target) {
    'image'        { Invoke-Image }
    'up'           { Invoke-Image; docker compose up -d --no-build }
    'down'         { docker compose down }
    'seed'         { docker compose run --rm api python -m app.memory.seed }
    'dev' {
        Invoke-Image
        docker compose up -d --no-build
        Write-Host 'API:     http://localhost:8000/api/health'
        Write-Host 'Browser: http://localhost:3000'
    }
    'test'         { docker compose run --rm api python -m pytest -q }
    'test-restart' { Push-Location ./backend; python -m pytest -q -m docker_control; Pop-Location }
    'lint'         { docker compose run --rm api ruff check app tests }
    'fmt'          { docker compose run --rm api ruff format app tests }
    'health'       { Invoke-RestMethod http://localhost:8000/api/health | ConvertTo-Json -Compress }
    'logs'         { docker compose logs -f api }
    'ps'           { docker compose ps }
    'clean'        { docker compose down -v }
}

exit $LASTEXITCODE
