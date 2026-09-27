import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega .env a partir da pasta backend/
backend_dir = Path(__file__).resolve().parent.parent.parent
env_file = backend_dir / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()

DEFAULT_JWT_SECRET = "sua-chave-secreta-super-segura-vturb-jwt-2026"
DEFAULT_SUPER_ADMIN_PASSWORD = "Admin123456!"
MIN_JWT_SECRET_LENGTH = 32


def _csv(value: str) -> list[str]:
    return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    PROJECT_NAME: str = "ProjetoVturb"
    # "production" liga as travas de segurança (boot recusa segredo padrão, docs fechadas)
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").strip().lower()
    # Origens liberadas no CORS (domínio do painel). Vazio em dev = qualquer origem.
    CORS_ORIGINS: list[str] = _csv(os.getenv("CORS_ORIGINS", ""))
    RATE_LIMIT_ENABLED: bool = _bool(os.getenv("RATE_LIMIT_ENABLED", "true"))
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://vturb_user:vturb_password@localhost:5434/vturb_db"
    )

    # Storage S3 genérico para vídeos e capas (Cloudflare R2, Backblaze B2, SeaweedFS...).
    # Vazio = usa as variáveis BACKBLAZE_* (compatibilidade com instalações antigas).
    STORAGE_ENDPOINT_URL: str = os.getenv("STORAGE_ENDPOINT_URL", "")
    # Endpoint usado nas URLs assinadas que o navegador acessa (em dev difere do interno do Docker)
    STORAGE_PRESIGN_ENDPOINT_URL: str = os.getenv("STORAGE_PRESIGN_ENDPOINT_URL", "")
    STORAGE_ACCESS_KEY_ID: str = os.getenv("STORAGE_ACCESS_KEY_ID", "")
    STORAGE_SECRET_ACCESS_KEY: str = os.getenv("STORAGE_SECRET_ACCESS_KEY", "")
    STORAGE_BUCKET: str = os.getenv("STORAGE_BUCKET", "")
    # Base pública dos arquivos (ex.: https://video.seudominio.com, domínio próprio do bucket R2)
    STORAGE_PUBLIC_URL: str = os.getenv("STORAGE_PUBLIC_URL", "")
    STORAGE_REGION: str = os.getenv("STORAGE_REGION", "auto")
    MAX_VIDEO_BYTES: int = int(os.getenv("MAX_VIDEO_BYTES", str(4 * 1024**3)))
    MAX_IMAGE_BYTES: int = int(os.getenv("MAX_IMAGE_BYTES", str(10 * 1024**2)))
    UPLOAD_PART_SIZE: int = int(os.getenv("UPLOAD_PART_SIZE", str(16 * 1024**2)))
    # Transcode para HLS pelo worker. Desligado por padrão: sem worker rodando, o vídeo ficaria "processando"
    HLS_ENABLED: bool = _bool(os.getenv("HLS_ENABLED", "false"))

    # Configurações do Backblaze B2 Storage
    BACKBLAZE_KEY_ID: str = os.getenv("BACKBLAZE_KEY_ID", "")
    BACKBLAZE_APPLICATION_KEY: str = os.getenv("BACKBLAZE_APPLICATION_KEY", "")
    BACKBLAZE_BUCKET_NAME: str = os.getenv("BACKBLAZE_BUCKET_NAME", "")
    BACKBLAZE_ENDPOINT_URL: str = os.getenv("BACKBLAZE_ENDPOINT_URL", "")
    BACKBLAZE_CDN_URL: str = os.getenv("BACKBLAZE_CDN_URL", "")

    # Credenciais do Super Admin
    SUPER_ADMIN_EMAIL: str = os.getenv("SUPER_ADMIN_EMAIL", "admin@vturb.com")
    SUPER_ADMIN_PASSWORD: str = os.getenv("SUPER_ADMIN_PASSWORD", DEFAULT_SUPER_ADMIN_PASSWORD)

    # Autenticação JWT
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", DEFAULT_JWT_SECRET)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_HOURS: int = int(
        os.getenv("JWT_ACCESS_TOKEN_EXPIRE_HOURS", "24h").lower().replace("h", "").strip()
    )

    # Integração Brevo (Envio de E-mails com Código de Validação)
    BREVO_API_KEY: str = os.getenv("BREVO_API_KEY", "")
    BREVO_SENDER_EMAIL: str = os.getenv("BREVO_SENDER_EMAIL", "noreply@vturb.com")
    BREVO_SENDER_NAME: str = os.getenv("BREVO_SENDER_NAME", "Smart VSL")

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


def production_config_problems(cfg) -> list[str]:
    """Lista o que impede subir em produção. Vazio = pode subir (ou não é produção)."""
    if getattr(cfg, "ENVIRONMENT", "") != "production":
        return []
    problems = []
    secret = cfg.JWT_SECRET_KEY or ""
    if secret == DEFAULT_JWT_SECRET or len(secret) < MIN_JWT_SECRET_LENGTH:
        problems.append(f"JWT_SECRET_KEY precisa ser aleatória e ter ao menos {MIN_JWT_SECRET_LENGTH} caracteres.")
    if not cfg.SUPER_ADMIN_PASSWORD or cfg.SUPER_ADMIN_PASSWORD == DEFAULT_SUPER_ADMIN_PASSWORD:
        problems.append("SUPER_ADMIN_PASSWORD não pode ficar vazia nem com o valor padrão.")
    origins = list(cfg.CORS_ORIGINS or [])
    if not origins or "*" in origins:
        problems.append("CORS_ORIGINS precisa listar o domínio do painel (sem '*').")
    return problems


def assert_production_ready(cfg) -> None:
    problems = production_config_problems(cfg)
    if problems:
        raise RuntimeError("Configuração insegura para produção: " + " | ".join(problems))


settings = Settings()
