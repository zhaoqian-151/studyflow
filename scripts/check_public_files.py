"""Audit the public source set without printing secret values or accessing remote services."""

import json
import re
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = ["app", "tests", "scripts", "migrations", "docs", "examples", ".github"]
ROOT_FILES = [
    ".gitignore",
    ".gitattributes",
    ".dockerignore",
    ".env.example",
    "README.md",
    "CONTRIBUTING.md",
    "THIRD_PARTY_NOTICES.md",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements.lock.txt",
    "pyproject.toml",
    "alembic.ini",
    "compose.yaml",
    "Dockerfile",
    "start.ps1",
    "start.sh",
]
TOKEN = re.compile(rb"(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-[A-Za-z0-9_-]{25,})")


def public_files():
    paths = [ROOT / name for name in ROOT_FILES if (ROOT / name).is_file()]
    for directory in DIRECTORIES:
        for path in (ROOT / directory).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}:
                paths.append(path)
    return sorted(set(paths))


def main():
    private = dotenv_values(ROOT / ".env") if (ROOT / ".env").exists() else {}
    secrets = [
        (name, value.encode())
        for name, value in private.items()
        if value and len(value) >= 12 and any(part in name.upper() for part in ["KEY", "PASSWORD", "TOKEN", "SECRET"])
    ]
    issues, size = [], 0
    paths = public_files()
    for path in paths:
        content = path.read_bytes()
        size += len(content)
        relative = path.relative_to(ROOT).as_posix()
        if path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".dump", ".pem", ".key"} or (
            path.name.startswith(".env") and path.name != ".env.example"
        ):
            issues.append({"file": relative, "issue": "private_file_type"})
        for name, value in secrets:
            if value in content:
                issues.append({"file": relative, "issue": "matches_local_secret", "variable": name})
        if TOKEN.search(content):
            issues.append({"file": relative, "issue": "possible_access_token"})
    print(
        json.dumps(
            {
                "status": "passed" if not issues else "failed",
                "files": len(paths),
                "total_bytes": size,
                "issues": issues,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if issues:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
