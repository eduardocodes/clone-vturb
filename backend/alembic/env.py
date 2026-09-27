"""Ambiente do Alembic.

A conexão pode vir pronta de ``app.core.migrations.run_migrations`` (via
``config.attributes["connection"]``, já com o advisory lock), ou ser aberta aqui
a partir da URL configurada (uso direto da CLI ``alembic``).
"""
from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import settings
from app.core.database import Base
from app.core.db_url import engine_url
import app.models.backup  # noqa: F401
import app.models.job  # noqa: F401
import app.models.metrics  # noqa: F401
import app.models.user  # noqa: F401
import app.models.video  # noqa: F401

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    return engine_url(config.get_main_option("sqlalchemy.url") or settings.DATABASE_URL)


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_with_connection(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run_with_connection(connection)
        return

    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    try:
        with engine.connect() as conn:
            _run_with_connection(conn)
            conn.commit()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
