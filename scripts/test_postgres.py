"""Run pytest against a new disposable PostgreSQL database, never the application database."""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
from sqlalchemy.engine import URL, make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import settings  # noqa: E402


def main():
    if not settings.postgres_password:
        raise SystemExit("Local POSTGRES_PASSWORD is required. Run scripts/setup_postgres.py first.")
    database = "studyflow_test_" + uuid4().hex
    url = URL.create(
        "postgresql+psycopg",
        username="studyflow",
        password=settings.postgres_password,
        host="127.0.0.1",
        port=5433,
        database=database,
    )
    active = make_url(settings.database_url)
    if active.get_backend_name() == "postgresql" and active.database == database:
        raise SystemExit("Test database unexpectedly matches application database.")
    admin = psycopg.connect(
        host="127.0.0.1",
        port=5433,
        user="studyflow",
        password=settings.postgres_password,
        dbname="postgres",
        autocommit=True,
    )
    created = False
    try:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        created = True
        environment = {
            **os.environ,
            "TEST_DATABASE_URL": url.render_as_string(hide_password=False),
            "AI_API_KEY": "",
            "EMBEDDING_API_KEY": "",
        }
        if sys.argv[1:] == ["--browser"]:
            environment["BROWSER_TEST_DATABASE_URL"] = url.render_as_string(hide_password=False)
            arguments = [sys.executable, "scripts/browser_smoke.py"]
        else:
            arguments = [sys.executable, "-m", "pytest", *(sys.argv[1:] or ["-q", "--tb=short"])]
        result = subprocess.run(
            arguments,
            cwd=ROOT,
            env=environment,
            check=False,
        )
    finally:
        # Drop only the randomly generated database successfully created by this invocation.
        if created and database.startswith("studyflow_test_"):
            admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()",
                (database,),
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))
        admin.close()
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
