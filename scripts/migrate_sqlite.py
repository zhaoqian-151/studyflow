"""Snapshot SQLite, transactionally copy into an empty PostgreSQL database, verify, then optionally activate.

Stop the application before running this command to avoid writes after the snapshot.
No model API calls are made; existing vectors are preserved.
"""

import argparse
import hashlib
import json
import math
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import set_key
from sqlalchemy import DateTime, func, insert, select
from sqlalchemy.engine import URL, make_url

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import models  # noqa: E402, F401
from app.config import VECTOR_DIMENSIONS, settings  # noqa: E402
from app.database import Base, make_engine  # noqa: E402
from app.schema import upgrade_schema  # noqa: E402


def normalize(value):
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or timezone.utc).astimezone(timezone.utc).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(item) for item in value]
    return value


def checksum(rows):
    # Vectors are compared numerically separately because pgvector stores float32.
    encoded = sorted(
        json.dumps(
            normalize({key: value for key, value in row.items() if key != "embedding"}),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        for row in rows
    )
    return hashlib.sha256("\n".join(encoded).encode()).hexdigest()


def snapshot(source: Path, destination: Path):
    if not source.is_file():
        raise RuntimeError(f"Source SQLite database does not exist: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as origin:
        with sqlite3.connect(destination) as backup:
            origin.backup(backup)


def copy_and_verify(source_engine, target_engine):
    if target_engine.dialect.name != "postgresql":
        raise RuntimeError("Migration target must be PostgreSQL.")
    upgrade_schema(target_engine)
    tables = list(Base.metadata.sorted_tables)
    with source_engine.connect() as origin:
        payload = {table.name: [dict(row) for row in origin.execute(select(table)).mappings()] for table in tables}
    for table in tables:
        for row in payload[table.name]:
            for column in table.columns:
                value = row.get(column.name)
                if isinstance(column.type, DateTime) and value is not None and value.tzinfo is None:
                    row[column.name] = value.replace(tzinfo=timezone.utc)
            vector = row.get("embedding")
            if vector is not None and (len(vector) != VECTOR_DIMENSIONS or not all(math.isfinite(v) for v in vector)):
                raise RuntimeError(f"Invalid existing vector in chunk {row.get('id')}; source remains unchanged.")
    report = {}
    with target_engine.begin() as target:
        if any(target.scalar(select(func.count()).select_from(table)) for table in tables):
            raise RuntimeError("Target has business data. Refusing to overwrite or merge it.")
        for table in tables:
            rows = payload[table.name]
            for offset in range(0, len(rows), 200):
                target.execute(insert(table), rows[offset : offset + 200])
            copied = [dict(row) for row in target.execute(select(table)).mappings()]
            source_hash, destination_hash = checksum(rows), checksum(copied)
            if len(rows) != len(copied) or source_hash != destination_hash:
                raise RuntimeError(f"Content verification failed for {table.name}; transaction rolled back.")
            if table.name == "chunks":
                destinations = {row["id"]: row for row in copied}
                for row in rows:
                    before, after = row["embedding"], destinations[row["id"]]["embedding"]
                    if (before is None) != (after is None):
                        raise RuntimeError("Vector nullability mismatch; transaction rolled back.")
                    if before is not None and (
                        len(before) != len(after)
                        or not all(math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-7) for a, b in zip(before, after))
                    ):
                        raise RuntimeError("Vector verification failed; transaction rolled back.")
            report[table.name] = {
                "source_rows": len(rows),
                "target_rows": len(copied),
                "checksum": source_hash,
                "verified": True,
            }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "data" / "studyflow.db")
    parser.add_argument("--activate", action="store_true", help="Switch .env DATABASE_URL only after all checks pass.")
    args = parser.parse_args()
    if not settings.postgres_password:
        raise SystemExit("Run python scripts/setup_postgres.py first.")
    target_url = make_url(settings.database_url)
    if target_url.get_backend_name() != "postgresql":
        target_url = URL.create(
            "postgresql+psycopg",
            username="studyflow",
            password=settings.postgres_password,
            host="127.0.0.1",
            port=5433,
            database="studyflow",
        )
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = ROOT / "data" / "backups" / f"studyflow-sqlite-{timestamp}.db"
    snapshot(args.source, backup)
    source_engine = make_engine(URL.create("sqlite", database=str(backup)))
    target_engine = make_engine(target_url)
    try:
        report = copy_and_verify(source_engine, target_engine)
    finally:
        source_engine.dispose()
        target_engine.dispose()
    manifest = {
        "backup": str(backup),
        "target_database": target_url.database,
        "vector_dimensions": VECTOR_DIMENSIONS,
        "tables": report,
        "activated": args.activate,
    }
    report_path = backup.with_suffix(".json")
    report_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.activate:
        set_key(str(ROOT / ".env"), "DATABASE_URL", target_url.render_as_string(hide_password=False))
    print(
        json.dumps(
            {
                "status": "verified",
                "backup": str(backup),
                "report": str(report_path),
                "rows": {name: item["target_rows"] for name, item in report.items()},
                "activated": args.activate,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
