"""Boot do container: migrations e super admin rodam uma vez, fora dos workers do uvicorn."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import bootstrap
from app.main import app


def test_bootstrap_roda_migrations_antes_do_super_admin():
    calls = []
    with patch.object(bootstrap, "run_migrations", side_effect=lambda: calls.append("migrations")), \
         patch.object(bootstrap, "init_super_admin", side_effect=lambda: calls.append("super_admin")):
        bootstrap.main()
    assert calls == ["migrations", "super_admin"]


def test_bootstrap_para_se_migration_falhar():
    with patch.object(bootstrap, "run_migrations", side_effect=RuntimeError("boom")), \
         patch.object(bootstrap, "init_super_admin") as super_admin:
        try:
            bootstrap.main()
            raised = False
        except RuntimeError:
            raised = True
    assert raised
    super_admin.assert_not_called()


def test_subir_a_api_nao_mexe_no_schema():
    with patch("app.core.migrations.run_migrations") as migrations, \
         patch("app.main.init_super_admin") as super_admin:
        with TestClient(app):
            pass
    migrations.assert_not_called()
    super_admin.assert_not_called()
