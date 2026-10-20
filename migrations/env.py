from alembic import context

from app import models  # noqa: F401
from app.config import settings
from app.database import Base, make_engine

config = context.config
target_metadata = Base.metadata


def configure(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    configure(config.attributes["connection"])
else:
    engine = make_engine(settings.database_url)
    with engine.connect() as connection:
        configure(connection)
    engine.dispose()
