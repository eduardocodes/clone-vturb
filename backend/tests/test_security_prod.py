"""Endurecimento para produção: segredos, docs, CORS, upload, rate limit e vazamento de erro."""
import io
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import bootstrap
from app.api.deps import get_current_user
from app.core.config import DEFAULT_JWT_SECRET, DEFAULT_SUPER_ADMIN_PASSWORD, production_config_problems
from app.core.rate_limit import FixedWindowLimiter, limiter
from app.main import app, create_app
from app.models.user import User

STRONG_SECRET = "x" * 48


def _cfg(**overrides):
    base = dict(
        ENVIRONMENT="production",
        JWT_SECRET_KEY=STRONG_SECRET,
        SUPER_ADMIN_PASSWORD="Senha-Forte-2026!",
        CORS_ORIGINS=["https://painel.exemplo.com"],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# --- SEC-01: segredos padrão bloqueiam o boot em produção -----------------------

def test_config_de_producao_valida_nao_tem_problemas():
    assert production_config_problems(_cfg()) == []


@pytest.mark.parametrize(
    "overrides, trecho",
    [
        ({"JWT_SECRET_KEY": DEFAULT_JWT_SECRET}, "JWT_SECRET_KEY"),
        ({"JWT_SECRET_KEY": "curta"}, "JWT_SECRET_KEY"),
        ({"SUPER_ADMIN_PASSWORD": DEFAULT_SUPER_ADMIN_PASSWORD}, "SUPER_ADMIN_PASSWORD"),
        ({"SUPER_ADMIN_PASSWORD": ""}, "SUPER_ADMIN_PASSWORD"),
        ({"CORS_ORIGINS": []}, "CORS_ORIGINS"),
        ({"CORS_ORIGINS": ["*"]}, "CORS_ORIGINS"),
    ],
)
def test_config_de_producao_insegura_e_apontada(overrides, trecho):
    problems = production_config_problems(_cfg(**overrides))
    assert any(trecho in p for p in problems)


def test_config_de_dev_nao_e_bloqueada():
    assert production_config_problems(_cfg(ENVIRONMENT="development", JWT_SECRET_KEY=DEFAULT_JWT_SECRET)) == []


def test_bootstrap_recusa_subir_com_segredo_padrao_em_producao():
    insecure = _cfg(JWT_SECRET_KEY=DEFAULT_JWT_SECRET)
    with patch.object(bootstrap, "settings", insecure), \
         patch.object(bootstrap, "run_migrations") as migrations:
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            bootstrap.main()
    migrations.assert_not_called()


# --- SEC-04: documentação da API fechada em produção ----------------------------

def test_docs_desligadas_em_producao():
    client = TestClient(create_app(_cfg()))
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404
    assert "docs" not in client.get("/").json()


def test_docs_ligadas_em_dev():
    client = TestClient(create_app(_cfg(ENVIRONMENT="development", CORS_ORIGINS=[])))
    assert client.get("/openapi.json").status_code == 200


# --- SEC-03: CORS só para o domínio do painel, sem credentials ------------------

def _preflight(client, origin):
    return client.options(
        "/videos/",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )


def test_cors_libera_o_painel_sem_credentials():
    client = TestClient(create_app(_cfg()))
    res = _preflight(client, "https://painel.exemplo.com")
    assert res.headers.get("access-control-allow-origin") == "https://painel.exemplo.com"
    assert "access-control-allow-credentials" not in res.headers


def test_cors_nega_origem_desconhecida():
    client = TestClient(create_app(_cfg()))
    res = _preflight(client, "https://site-malicioso.com")
    assert "access-control-allow-origin" not in res.headers


# --- SEC-05: token na query só vale para o download de backup -------------------

def test_token_na_query_nao_autentica_rotas_comuns():
    client = TestClient(app)
    from app.core.security import create_access_token

    token = create_access_token(data={"sub": "qualquer"})
    assert client.get(f"/videos/?token={token}").status_code == 401


# --- SEC-06: upload recusa SVG e tipo divergente -------------------------------

@pytest.fixture
def logged_client():
    app.dependency_overrides[get_current_user] = lambda: User(id="u1", email="u@x.com")
    yield TestClient(app)
    app.dependency_overrides.pop(get_current_user, None)


def test_upload_recusa_svg(logged_client):
    files = {"file": ("capa.svg", io.BytesIO(b"<svg onload=alert(1)>"), "image/svg+xml")}
    assert logged_client.post("/videos/upload", files=files).status_code == 400


def test_upload_recusa_extensao_de_video_com_mime_de_outra_coisa(logged_client):
    files = {"file": ("video.mp4", io.BytesIO(b"<html>"), "text/html")}
    assert logged_client.post("/videos/upload", files=files).status_code == 400


# --- SEC-07: rate limit ---------------------------------------------------------

@pytest.fixture
def rate_limit_on():
    limiter.reset()
    limiter.enabled = True
    yield
    limiter.enabled = False
    limiter.reset()


def test_login_bloqueia_depois_do_limite(rate_limit_on):
    client = TestClient(app)
    body = {"email": "ninguem@exemplo.com", "password": "errada"}
    headers = {"CF-Connecting-IP": "203.0.113.7"}
    for _ in range(10):
        assert client.post("/auth/login", json=body, headers=headers).status_code == 401
    blocked = client.post("/auth/login", json=body, headers=headers)
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    # Outro IP não é afetado
    other = client.post("/auth/login", json=body, headers={"CF-Connecting-IP": "203.0.113.8"})
    assert other.status_code == 401


def test_limiter_libera_de_novo_quando_a_janela_vira():
    now = [1000.0]
    lim = FixedWindowLimiter(clock=lambda: now[0])
    assert all(lim.hit("k", limit=2, window=60)[0] for _ in range(2))
    allowed, retry_after = lim.hit("k", limit=2, window=60)
    assert not allowed and 0 < retry_after <= 60
    now[0] += 61
    assert lim.hit("k", limit=2, window=60)[0]


def test_limiter_tem_memoria_limitada():
    lim = FixedWindowLimiter(clock=lambda: 0.0, max_keys=100)
    for i in range(1000):
        lim.hit(f"ip-{i}", limit=5, window=60)
    assert lim.size() <= 100


# --- SEC-09: erro interno não vaza para o cliente -------------------------------

def test_erro_de_backup_nao_vaza_detalhe():
    from app.api import backups
    from app.api.users import require_super_admin

    app.dependency_overrides[require_super_admin] = lambda: User(id="a", email="a@x.com", is_super_admin=True)
    try:
        with patch.object(backups.BackupManager, "create_database_dump", side_effect=Exception("senha=segredo123")):
            res = TestClient(app).post("/backups/create")
    finally:
        app.dependency_overrides.pop(require_super_admin, None)
    assert res.status_code >= 400
    assert "segredo123" not in res.text
