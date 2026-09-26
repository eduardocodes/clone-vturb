"""Helpers de banco para os testes (sem efeitos colaterais no import)."""
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.db_url import engine_url

DEFAULT_DATABASE_URL = "postgresql://vturb_user:vturb_password@localhost:5434/vturb_db"


def derive_test_database_url(base_url: str, suffix: str = "test") -> str:
    """Troca o nome do banco da URL por ``<nome>_<suffix>``."""
    url = make_url(engine_url(base_url))
    return url.set(database=f"{url.database}_{suffix}").render_as_string(hide_password=False)


def recreate_database(database_url: str) -> None:
    """Apaga e recria o banco da URL. Só aceita bancos cujo nome termina em ``_test``."""
    url = make_url(engine_url(database_url))
    name = url.database or ""
    if not name.endswith("_test"):
        raise RuntimeError(f"Recusando recriar banco que não é de teste: {name!r}")

    admin_engine = create_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        admin_engine.dispose()
