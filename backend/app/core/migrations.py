"""Aplica as migrations do Alembic no boot (uma vez por container, não por worker).

Instalações anteriores ao Alembic têm as tabelas (criadas por ``create_all``) mas
não têm ``alembic_version``: nesse caso a baseline é carimbada antes do upgrade,
para não tentar recriar tabelas existentes.
"""
import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, pool, text

from app.core.config import settings
from app.core.db_url import engine_url

logger = logging.getLogger("projetovturb.migrations")

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
BASELINE_REVISION = "0001_baseline"
# Chave do pg_advisory_lock: impede dois containers migrando ao mesmo tempo
MIGRATION_LOCK_ID = 740_120_260_1


def alembic_config(database_url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    # "%" precisa ser escapado no ConfigParser do Alembic
    cfg.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return cfg


def run_migrations(database_url: str | None = None) -> None:
    url = engine_url(database_url or settings.DATABASE_URL)
    engine = create_engine(url, poolclass=pool.NullPool)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT pg_advisory_lock(:id)"), {"id": MIGRATION_LOCK_ID})
            conn.commit()
            try:
                cfg = alembic_config(url)
                cfg.attributes["connection"] = conn
                tables = set(inspect(conn).get_table_names())
                if "alembic_version" not in tables and "videos" in tables:
                    logger.info("Banco sem alembic_version: carimbando baseline %s", BASELINE_REVISION)
                    command.stamp(cfg, BASELINE_REVISION)
                    conn.commit()
                command.upgrade(cfg, "head")
                conn.commit()
            finally:
                conn.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": MIGRATION_LOCK_ID})
                conn.commit()
    finally:
        engine.dispose()
