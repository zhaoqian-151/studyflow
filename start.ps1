$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create virtual environment. Install Python 3.12+.' }
}
& $projectPython -c 'import fastapi, sqlalchemy, uvicorn, pydantic_settings, multipart, pypdf, docx, psycopg, pgvector, alembic'
if ($LASTEXITCODE -ne 0) {
    & $projectPython -m pip install -r requirements.lock.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
& $projectPython scripts/setup_postgres.py
if ($LASTEXITCODE -ne 0) { throw 'Failed to prepare PostgreSQL configuration.' }
$databaseStatusJson = & $projectPython scripts/database_status.py
if ($LASTEXITCODE -ne 0) { throw 'Failed to read database configuration. Check DATABASE_URL in .env.' }
$databaseStatus = $databaseStatusJson | ConvertFrom-Json
if ($databaseStatus.start_local_postgres) {
    $dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
    $dockerExecutable = if ($dockerCommand) { $dockerCommand.Source } else { Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe' }
    if (-not (Test-Path -LiteralPath $dockerExecutable)) {
        $dockerExecutable = Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin\docker.exe'
    }
    if (-not (Test-Path -LiteralPath $dockerExecutable)) { throw 'Docker CLI not found. Install/start Docker Desktop.' }
    & $dockerExecutable compose up -d --wait postgres
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL startup failed. Check Docker Desktop.' }
}
if ($databaseStatus.backend -eq 'postgresql') {
    & $projectPython -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
}
Write-Host 'Starting StudyFlow: http://127.0.0.1:8000 | API: http://127.0.0.1:8000/docs'
& $projectPython -m uvicorn app.main:app --reload --reload-include '.env' --host 127.0.0.1 --port 8000 --ws-max-size 8192
if ($LASTEXITCODE -ne 0) { throw 'StudyFlow failed to start. See the error above.' }
