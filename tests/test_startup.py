"""Exercise native argument passing with the actual Windows PowerShell executables."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell argument passing regression")
@pytest.mark.parametrize("shell", ["powershell.exe", "pwsh.exe"])
def test_database_probe_with_windows_shell(shell):
    executable = shutil.which(shell)
    if not executable:
        pytest.skip(f"{shell} is not installed")
    python = sys.executable.replace("'", "''")
    helper = str(ROOT / "scripts" / "database_status.py").replace("'", "''")
    command = f"& '{python}' '{helper}'; exit $LASTEXITCODE"
    environment = {
        **os.environ,
        "DATABASE_URL": "postgresql+psycopg://example:startup_probe_secret@127.0.0.1:5433/studyflow",
    }
    result = subprocess.run(
        [executable, "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"backend": "postgresql", "start_local_postgres": True}
    assert "startup_probe_secret" not in result.stdout + result.stderr


def test_database_probe_rejects_invalid_url_without_exposing_input():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "database_status.py")],
        cwd=ROOT,
        env={**os.environ, "DATABASE_URL": "invalid-url-with-private-startup-secret"},
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "Check DATABASE_URL" in result.stderr
    assert "private-startup-secret" not in result.stdout + result.stderr
