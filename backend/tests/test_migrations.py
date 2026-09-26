"""Migrations via Alembic: banco novo, instalação antiga (sem alembic_version) e drift."""
import os

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.core.database import Base
from app.core.migrations import BASELINE_REVISION, alembic_config, run_migrations
from tests.db_utils import derive_test_database_url, recreate_database

import app.models.backup  # noqa: F401
import app.models.metrics  # noqa: F401
import app.models.user  # noqa: F401
import app.models.video  # noqa: F401

EXPECTED_TABLES = {
    "videos",
    "video_analytics",
    "users",
    "user_invites",
    "email_verification_codes",
    "password_reset_tokens",
    "backup_records",
    "backup_schedules",
}


def _head_revision(url: str) -> str:
    return ScriptDirectory.from_config(alembic_config(url)).get_current_head()


def _current_revision(engine) -> str | None:
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


TEST_DATABASE_URL = os.environ["DATABASE_URL"]


@pytest.fixture
def scratch_db():
    url = derive_test_database_url(TEST_DATABASE_URL, "mig_test")
    recreate_database(url)
    engine = create_engine(url)
    yield url, engine
    engine.dispose()


def test_banco_novo_recebe_todas_as_tabelas_e_fica_no_head(scratch_db):
    url, engine = scratch_db

    run_migrations(url)

    tables = set(inspect(engine).get_table_names())
    assert EXPECTED_TABLES <= tables
    assert _current_revision(engine) == _head_revision(url)


def test_instalacao_antiga_sem_alembic_e_carimbada_e_preserva_dados(scratch_db):
    url, engine = scratch_db
    # Simula uma instalação feita antes do Alembic: schema da baseline, sem alembic_version
    from alembic import command

    command.upgrade(alembic_config(url), BASELINE_REVISION)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE alembic_version"))
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO videos (id, title, video_url, duration) VALUES ('v-legado', 'Legado', 'https://x/v.mp4', 10)")
        )

    run_migrations(url)

    assert _current_revision(engine) == _head_revision(url)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT title FROM videos WHERE id = 'v-legado'")).scalar() == "Legado"


def test_rodar_duas_vezes_e_idempotente(scratch_db):
    url, engine = scratch_db

    run_migrations(url)
    run_migrations(url)

    assert _current_revision(engine) == _head_revision(url)


def test_baseline_e_a_primeira_revisao(scratch_db):
    url, _ = scratch_db
    script = ScriptDirectory.from_config(alembic_config(url))
    assert script.get_revision(BASELINE_REVISION).down_revision is None


def test_schema_migrado_bate_com_os_models():
    """Protege contra drift: todo model novo precisa de migration."""
    engine = create_engine(TEST_DATABASE_URL)
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn, opts={"compare_type": True})
            diff = compare_metadata(ctx, Base.metadata)
    finally:
        engine.dispose()
    assert diff == []


def test_0003_preserva_eventos_existentes(scratch_db):
    from alembic import command

    url, engine = scratch_db
    command.upgrade(alembic_config(url), "0002_video_storage")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO videos (id, title, video_url, duration) VALUES ('v1', 'V', 'https://x', 10)"))
        for _ in range(3):
            conn.execute(text(
                "INSERT INTO video_analytics (video_id, event_type, session_id, created_at, watch_time_seconds) "
                "VALUES ('v1', 'play', 's1', '2026-09-20 10:00:00+00', 0)"
            ))

    run_migrations(url)

    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM video_analytics")).scalar() == 3
        assert "video_metrics_daily" in inspect(conn).get_table_names()
