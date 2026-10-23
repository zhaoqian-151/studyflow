"""Describe startup requirements without exposing database credentials to the shell."""

import json
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    try:
        from app.config import settings

        url = make_url(settings.database_url)
        backend = url.get_backend_name()
        if backend == "postgres":
            backend = "postgresql"
        status = {
            "backend": backend,
            "start_local_postgres": backend == "postgresql"
            and url.host in {"127.0.0.1", "localhost"}
            and url.port == 5433,
        }
    except Exception:
        # A URL parsing error can include the original input, including its password.
        raise SystemExit("Cannot read database configuration. Check DATABASE_URL in .env.") from None
    print(json.dumps(status))


if __name__ == "__main__":
    main()
