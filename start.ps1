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
$localDatabase = & $projectPython -c 'from app.config import settings; from sqlalchemy.engine import make_url; u=make_url(settings.database_url); print(int(u.get_backend_name() == "postgresql" and u.host in ("127.0.0.1", "localhost") and u.port == 5433))'
if ($localDatabase -eq '1') {
    $dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
    $dockerExecutable = if ($dockerCommand) { $dockerCommand.Source } else { Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe' }
    if (-not (Test-Path -LiteralPath $dockerExecutable)) {
        $dockerExecutable = Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin\docker.exe'
    }
    if (-not (Test-Path -LiteralPath $dockerExecutable)) { throw 'Docker CLI not found. Install/start Docker Desktop.' }
    & $dockerExecutable compose up -d --wait postgres
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL startup failed. Check Docker Desktop.' }
}
$postgresDatabase = & $projectPython -c 'from app.config import settings; from sqlalchemy.engine import make_url; print(int(make_url(settings.database_url).get_backend_name() == "postgresql"))'
if ($postgresDatabase -eq '1') {
    & $projectPython -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
}
Write-Host 'StudyFlow: http://127.0.0.1:8000 | API: http://127.0.0.1:8000/docs'
& $projectPython -m uvicorn app.main:app --reload --reload-include '.env' --host 127.0.0.1 --port 8000 --ws-max-size 8192
