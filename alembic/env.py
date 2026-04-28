import sys
sys.path.insert(0, "/app")

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

from app.core.database import Base

# Import all models so they register with Base.metadata
from app.models.venue import Venue  # noqa: F401
from app.models.document import Document  # noqa: F401
from app.models.chunk import Chunk  # noqa: F401
from app.models.query import Query  # noqa: F401
from app.models.query_source import QuerySource  # noqa: F401

config = context.config

# Override URL from environment if available
database_url = os.getenv(
    "DATABASE_URL_SYNC",
    config.get_main_option("sqlalchemy.url"),
)
config.set_main_option("sqlalchemy.url", database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()