import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

# Set before importing the application; tests never write the development database.
TEST_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_URL:
    parsed = make_url(TEST_URL)
    if parsed.get_backend_name() != "postgresql" or not (parsed.database or "").startswith("studyflow_test_"):
        raise RuntimeError("TEST_DATABASE_URL must use an isolated PostgreSQL database named studyflow_test_*.")
    os.environ["DATABASE_URL"] = TEST_URL
else:
    TEST_DIRECTORY = tempfile.TemporaryDirectory(prefix="studyflow-tests-")
    os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(TEST_DIRECTORY.name) / "test.db").replace("\\", "/")
os.environ["AI_API_KEY"] = ""
os.environ["EMBEDDING_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app, attempts  # noqa: E402
from app.schema import upgrade_schema  # noqa: E402


@pytest.fixture
def client():
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            Base.metadata.drop_all(connection)
            connection.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
        upgrade_schema(engine)
    else:
        Base.metadata.drop_all(engine)
    attempts.clear()
    with TestClient(app) as instance:
        yield instance


@pytest.fixture
def user(client):
    response = client.post(
        "/api/auth/register", json={"name": "学习者", "email": "learner@example.com", "password": "strong-pass-123"}
    )
    assert response.status_code == 201
    return response.json()
