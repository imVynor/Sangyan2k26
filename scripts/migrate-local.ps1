$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

$python = Join-Path $PWD "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "backend\.venv is missing. Create it and install dependencies first; see the Install dependencies section in README.md."
}

$backendEnv = Join-Path $PWD "backend\.env"
if (Test-Path $backendEnv) {
    $databaseLine = Get-Content $backendEnv | Where-Object { $_ -match '^\s*DATABASE_URL=(.*)$' } | Select-Object -First 1
    if ($databaseLine -match '^\s*DATABASE_URL=(.*)$') {
        $env:DATABASE_URL = $matches[1].Trim()
    }
}

Push-Location backend
try {
    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "Backend migrations failed."
    }
}
finally {
    Pop-Location
}

Push-Location ai
try {
    if ($env:DATABASE_URL) {
        $env:DATABASE_URL = $env:DATABASE_URL -replace "postgresql\+asyncpg", "postgresql+psycopg"
    }
    & $python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        throw "AI migrations failed."
    }
}
finally {
    Pop-Location
}

Write-Host "Local database migrations completed."
