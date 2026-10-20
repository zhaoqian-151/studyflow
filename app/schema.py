from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]


def migration_config():
    return Config(str(ROOT / "alembic.ini"))


def upgrade_schema(engine):
    config = migration_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def verify_schema(engine):
    expected = ScriptDirectory.from_config(migration_config()).get_current_head()
    with engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()
    if not expected or current != expected:
        raise RuntimeError("Database migration required: run python -m alembic upgrade head before starting.")
