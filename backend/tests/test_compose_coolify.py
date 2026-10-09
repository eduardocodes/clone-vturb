"""Contrato do compose usado no deploy pela Coolify (docker/docker-compose-coolify.yml)."""
from pathlib import Path

import pytest
import yaml

CANDIDATES = [
    Path("/docker/docker-compose-coolify.yml"),
    Path(__file__).resolve().parent.parent.parent / "docker" / "docker-compose-coolify.yml",
]


def _env_keys(service: dict) -> set[str]:
    env = service.get("environment") or {}
    if isinstance(env, dict):
        return set(env)
    return {item.split("=", 1)[0] for item in env}


@pytest.fixture(scope="module")
def compose() -> dict:
    path = next((p for p in CANDIDATES if p.exists()), None)
    assert path is not None, "docker/docker-compose-coolify.yml não encontrado"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_servicos_esperados(compose):
    assert {"postgres", "backend", "frontend"} <= set(compose["services"])


def test_imagens_sao_buildadas_do_proprio_repo(compose):
    for name, service in compose["services"].items():
        if name == "postgres":
            continue
        assert "build" in service, f"{name} deve ser buildado do repo"
        assert "aryalvesfernandes" not in str(service.get("image", ""))


def test_postgres_sem_porta_publicada_e_com_volume(compose):
    pg = compose["services"]["postgres"]
    assert "ports" not in pg
    assert any("/var/lib/postgresql/data" in v for v in pg["volumes"])
    assert "healthcheck" in pg


def test_backend_espera_postgres_saudavel(compose):
    depends = compose["services"]["backend"]["depends_on"]
    assert depends["postgres"]["condition"] == "service_healthy"


def test_frontend_recebe_so_a_url_da_api(compose):
    assert _env_keys(compose["services"]["frontend"]) == {"VITE_API_BASE_URL"}


def test_frontend_recebe_a_url_da_api_com_esquema(compose):
    # SERVICE_FQDN_* é só o host; sem https:// o painel chama um caminho relativo
    assert compose["services"]["frontend"]["environment"]["VITE_API_BASE_URL"] == "${SERVICE_URL_BACKEND}"


def test_sem_labels_de_swarm(compose):
    for name, service in compose["services"].items():
        assert "labels" not in (service.get("deploy") or {}), f"{name} não deve ter labels do Swarm"
        assert "hostname" not in service


def test_segredos_sem_valor_padrao(compose):
    backend_env = compose["services"]["backend"]["environment"]
    for key in ("JWT_SECRET_KEY", "SUPER_ADMIN_PASSWORD", "POSTGRES_PASSWORD"):
        value = str(backend_env.get(key, "")) if isinstance(backend_env, dict) else ""
        if key == "POSTGRES_PASSWORD":
            value = str(compose["services"]["postgres"]["environment"].get(key, ""))
        assert value.startswith("${"), f"{key} deve vir do ambiente da Coolify"
        assert ":-" not in value, f"{key} não pode ter valor padrão"


def test_backend_em_modo_producao_com_cors_definido(compose):
    env = compose["services"]["backend"]["environment"]
    assert env["ENVIRONMENT"] == "production"
    assert str(env["CORS_ORIGINS"]).startswith("${")


def test_worker_usa_a_mesma_imagem_e_espera_o_backend(compose):
    worker = compose["services"]["worker"]
    backend = compose["services"]["backend"]
    assert worker["build"] == backend["build"]
    command = worker["command"]
    assert "app.worker" in (" ".join(command) if isinstance(command, list) else command)
    # Migrations rodam no boot do backend: o worker só sobe depois dele saudável
    assert worker["depends_on"]["backend"]["condition"] == "service_healthy"
    assert worker["environment"]["DATABASE_URL"] == backend["environment"]["DATABASE_URL"]


def test_hls_ligado_na_api_e_no_worker_juntos(compose):
    # A API só enfileira transcode se HLS_ENABLED; quem processa é o worker
    backend = compose["services"]["backend"]["environment"]
    worker = compose["services"]["worker"]["environment"]
    assert backend["HLS_ENABLED"] == worker["HLS_ENABLED"] == "${HLS_ENABLED:-true}"


def test_worker_tem_limite_de_cpu_e_memoria_para_o_ffmpeg(compose):
    limits = compose["services"]["worker"]["deploy"]["resources"]["limits"]
    assert limits["cpus"] == "2"
    assert limits["memory"] == "1536M"


def test_backend_recebe_hash_da_chave_do_export_vazio_por_padrao(compose):
    # Sem a env, /api/v1/export/* responde 404 (export desligado)
    env = compose["services"]["backend"]["environment"]
    assert env["EXPORT_API_KEY_SHA256"] == "${EXPORT_API_KEY_SHA256:-}"
