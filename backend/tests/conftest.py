"""Configuração global da suíte de testes.

Os testes rodam num banco próprio (nome terminado em ``_test``), recriado a cada
execução e migrado via Alembic, para nunca escrever no banco de desenvolvimento.

Este módulo precisa ajustar ``DATABASE_URL`` ANTES de qualquer import de ``app``,
porque ``app.core.config`` e ``app.core.database`` leem a variável no import.
"""
import os

from tests.db_utils import DEFAULT_DATABASE_URL, derive_test_database_url, recreate_database

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or derive_test_database_url(
    os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
# Rate limit fica desligado na suíte; os testes de segurança ligam explicitamente
os.environ["RATE_LIMIT_ENABLED"] = "false"
# HLS fica desligado na suíte; os testes de HLS ligam explicitamente
os.environ["HLS_ENABLED"] = "false"
# Storage real nunca é usado na suíte (os testes injetam mocks); zera o que vier do compose
for _var in (
    "STORAGE_ENDPOINT_URL", "STORAGE_PRESIGN_ENDPOINT_URL", "STORAGE_ACCESS_KEY_ID",
    "STORAGE_SECRET_ACCESS_KEY", "STORAGE_BUCKET", "STORAGE_PUBLIC_URL",
):
    os.environ[_var] = ""

recreate_database(TEST_DATABASE_URL)

from app.core.migrations import run_migrations  # noqa: E402  (precisa vir depois do ajuste do env)

run_migrations(TEST_DATABASE_URL)
