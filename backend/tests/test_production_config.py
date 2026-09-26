# -*- coding: utf-8 -*-
import os
import yaml
from pathlib import Path
from app.core.config import Settings, settings
from app.main import init_db

def test_production_environment_variables_settings():
    """Valida se a classe Settings mapeia todas as variáveis de ambiente necessárias."""
    s = Settings()
    # 1. Banco de Dados
    assert hasattr(s, "DATABASE_URL")
    assert isinstance(s.DATABASE_URL, str)

    # 2. Super Admin
    assert hasattr(s, "SUPER_ADMIN_EMAIL")
    assert hasattr(s, "SUPER_ADMIN_PASSWORD")
    assert bool(s.SUPER_ADMIN_EMAIL)
    assert "@" in s.SUPER_ADMIN_EMAIL

    # 3. Autenticação JWT
    assert hasattr(s, "JWT_SECRET_KEY")
    assert hasattr(s, "JWT_ACCESS_TOKEN_EXPIRE_HOURS")
    assert isinstance(s.JWT_ACCESS_TOKEN_EXPIRE_HOURS, int)
    assert s.JWT_ACCESS_TOKEN_EXPIRE_HOURS == 24

    # 4. Backblaze B2 / S3
    assert hasattr(s, "BACKBLAZE_KEY_ID")
    assert hasattr(s, "BACKBLAZE_APPLICATION_KEY")
    assert hasattr(s, "BACKBLAZE_BUCKET_NAME")
    assert hasattr(s, "BACKBLAZE_ENDPOINT_URL")
    assert hasattr(s, "BACKBLAZE_CDN_URL")

    # 5. Brevo E-mails
    assert hasattr(s, "BREVO_API_KEY")
    assert hasattr(s, "BREVO_SENDER_EMAIL")
    assert hasattr(s, "BREVO_SENDER_NAME")

def test_init_db_runs_without_exceptions():
    """Valida se a função init_db cria/valida as tabelas com sucesso."""
    init_db()

def test_docker_compose_production_structure():
    """Valida se o docker-compose de produção contém estritamente backend e frontend."""
    # Procura compose na pasta docker/ ou no diretório do projeto
    possible_paths = [
        Path("/app/../docker/docker-compose-prod.yml"),
        Path("/docker/docker-compose-prod.yml"),
        Path(__file__).resolve().parent.parent.parent / "docker" / "docker-compose-prod.yml",
    ]
    compose_path = None
    for p in possible_paths:
        if p.exists():
            compose_path = p
            break

    if compose_path and compose_path.exists():
        with open(compose_path, "r", encoding="utf-8") as f:
            compose_data = yaml.safe_load(f)

        assert "services" in compose_data
        services = compose_data["services"]

        # Deve conter apenas backend e frontend
        assert "backend" in services
        assert "frontend" in services
        assert "postgres" not in services, "A stack de produção não deve conter o container postgres local."

        # Backend checks
        backend = services["backend"]
        assert "build" in backend
        assert "healthcheck" in backend
        assert backend.get("networks") == ["network_swarm_public"]
        assert backend.get("hostname") == "{{.Service.Name}}.{{.Task.Slot}}"
        assert "environment" in backend
        assert "deploy" in backend
        assert any("traefik.enable=true" in l for l in backend["deploy"].get("labels", []))

        # Frontend checks
        frontend = services["frontend"]
        assert "build" in frontend
        assert frontend.get("networks") == ["network_swarm_public"]
        assert frontend.get("hostname") == "{{.Service.Name}}.{{.Task.Slot}}"
        assert "environment" in frontend
        assert "deploy" in frontend
        assert any("traefik.enable=true" in l for l in frontend["deploy"].get("labels", []))

        # Valida que só existe 1 rede e que ela é a network_swarm_public
        assert "networks" in compose_data
        assert list(compose_data["networks"].keys()) == ["network_swarm_public"]
        assert compose_data["networks"]["network_swarm_public"].get("external") is True

        # O frontend recebe só a URL da API: nenhum segredo do backend vaza para ele
        backend_env = dict(e.split("=", 1) for e in backend["environment"])
        frontend_env_keys = [e.split("=")[0] if isinstance(e, str) else e for e in frontend["environment"]]
        assert set(frontend_env_keys) == {"VITE_API_BASE_URL"}

        # Backend sobe em modo produção, sem segredo com valor padrão
        assert backend_env["ENVIRONMENT"] == "production"
        for key in ("JWT_SECRET_KEY", "SUPER_ADMIN_PASSWORD", "CORS_ORIGINS"):
            assert ":-" not in backend_env[key], f"{key} não pode ter valor padrão"
