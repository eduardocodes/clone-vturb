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
