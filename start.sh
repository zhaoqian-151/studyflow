#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
if [ ! -f .venv/bin/python ]; then
    python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import fastapi, sqlalchemy, psycopg, pgvector, alembic' >/dev/null 2>&1; then
    .venv/bin/python -m pip install -r requirements.lock.txt
fi
.venv/bin/python scripts/setup_postgres.py
docker compose up -d --wait postgres
.venv/bin/python -m alembic upgrade head
exec .venv/bin/python -m uvicorn app.main:app --reload --reload-include .env --host 127.0.0.1 --port 8000 --ws-max-size 8192
