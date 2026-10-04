$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

$python = Join-Path $PWD "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "backend\.venv is missing. Create it and install dependencies first; see the Install dependencies section in README.md."
}

$psql = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psql) {
    throw "psql was not found on PATH. Install PostgreSQL and add its bin directory to PATH."
}

$envFile = Join-Path $PWD "backend\.env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $PWD "backend\.env.example") $envFile
    Write-Host "Created backend\.env from backend\.env.example."
}

$values = @{}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
        $values[$matches[1].Trim()] = $matches[2].Trim()
    }
}

foreach ($name in @("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_SERVER", "POSTGRES_PORT", "POSTGRES_DB")) {
    if (-not $values.ContainsKey($name) -or [string]::IsNullOrWhiteSpace($values[$name])) {
        throw "$name is missing from backend\.env."
    }
}

if ($values["POSTGRES_DB"] -notmatch '^[A-Za-z_][A-Za-z0-9_]*$') {
    throw "POSTGRES_DB must contain only letters, numbers, and underscores."
}

$env:PGPASSWORD = $values["POSTGRES_PASSWORD"]
$psqlArgs = @("-h", $values["POSTGRES_SERVER"], "-p", $values["POSTGRES_PORT"], "-U", $values["POSTGRES_USER"])

& $psql.Source @psqlArgs -d postgres -v ON_ERROR_STOP=1 -tAc "SELECT 1" *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Could not connect to PostgreSQL. Check the service, credentials, host, and port in backend\.env."
}

$databaseExists = (& $psql.Source @psqlArgs -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$($values["POSTGRES_DB"])'").Trim()
if ($databaseExists -ne "1") {
    & $psql.Source @psqlArgs -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $($values["POSTGRES_DB"])" *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create database $($values["POSTGRES_DB"])."
    }
    Write-Host "Created database $($values["POSTGRES_DB"])."
}

$vectorAvailable = (& $psql.Source @psqlArgs -d $values["POSTGRES_DB"] -tAc "SELECT 1 FROM pg_available_extensions WHERE name = 'vector'").Trim()
if ($vectorAvailable -ne "1") {
    throw "The PostgreSQL vector extension is not installed. Install pgvector for this PostgreSQL instance, then run npm run setup:local again."
}

& (Join-Path $PSScriptRoot "migrate-local.ps1")
if ($LASTEXITCODE -ne 0) {
    throw "Local database setup failed during migrations."
}

Write-Host "Local setup is ready. Start the application with: npm run dev"
