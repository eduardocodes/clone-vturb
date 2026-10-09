import logging
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.core.config import assert_production_ready, settings
from app.core.database import SessionLocal
from app.models.user import User
from app.core.security import hash_password, verify_password
from app.api.health import router as health_router
from app.api.videos import router as videos_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.backups import router as backups_router
from app.api.uploads import router as uploads_router
from app.api.attribution import router as attribution_router
from app.api.export import router as export_router

logger = logging.getLogger("projetovturb")
logging.basicConfig(level=logging.INFO)

def init_super_admin():
    """Garante que a conta de Super Admin configurada no .env exista e esteja atualizada."""
    email = settings.SUPER_ADMIN_EMAIL.strip().lower()
    password = settings.SUPER_ADMIN_PASSWORD
    if not email or not password:
        logger.warning("SUPER_ADMIN_EMAIL ou SUPER_ADMIN_PASSWORD não configurados no .env")
        return

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email.ilike(email)).first()
        if not user:
            logger.info(f"Criando conta inicial de Super Admin: {email}")
            user = User(
                email=email,
                name="Super Admin",
                password_hash=hash_password(password),
                role="super_admin",
                is_super_admin=True
            )
            db.add(user)
            db.commit()
            logger.info("Conta de Super Admin criada com sucesso!")
        else:
            # Sincroniza senha se mudou no .env
            if not verify_password(password, user.password_hash):
                logger.info(f"Atualizando credenciais do Super Admin: {email}")
                user.password_hash = hash_password(password)
            user.role = "super_admin"
            user.is_super_admin = True
            if not user.name:
                user.name = "Super Admin"
            db.commit()
            logger.info("Credenciais do Super Admin sincronizadas com sucesso!")
    except Exception as exc:
        logger.error(f"Erro ao inicializar conta de Super Admin: {exc}")
        db.rollback()
    finally:
        db.close()

def init_db():
    """Leva o schema do banco ao head do Alembic (mantido por compatibilidade)."""
    from app.core.migrations import run_migrations
    run_migrations()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema e Super Admin são preparados por `python -m app.bootstrap` antes do
    # uvicorn subir, uma vez por container (não por worker). Aqui só a trava de
    # segurança: cada worker se recusa a subir com configuração insegura.
    assert_production_ready(settings)
    yield


def create_app(cfg=settings) -> FastAPI:
    is_production = cfg.ENVIRONMENT == "production"
    docs_kwargs = (
        {"docs_url": None, "redoc_url": None, "openapi_url": None} if is_production else {}
    )
    application = FastAPI(
        title=cfg.PROJECT_NAME if hasattr(cfg, "PROJECT_NAME") else settings.PROJECT_NAME,
        description="API do ProjetoVturb desenvolvida com FastAPI e PostgreSQL",
        version="0.1.0",
        lifespan=lifespan,
        **docs_kwargs,
    )

    # Exception Handler Global (regra obrigatória)
    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Erro inesperado em {request.method} {request.url.path}: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Erro interno do servidor. Tente novamente mais tarde."}
        )

    # CORS: autenticação é por header Bearer (não cookie), então sem credentials.
    # O painel e o embed rodam no mesmo domínio do frontend; em dev, sem lista = qualquer origem.
    origins = list(cfg.CORS_ORIGINS or []) or (["*"] if not is_production else [])
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static files directory
    static_dir = Path(__file__).resolve().parent.parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    application.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(videos_router)
    application.include_router(uploads_router)
    application.include_router(users_router)
    application.include_router(backups_router, prefix="/backups", tags=["Backups"])
    application.include_router(attribution_router)
    application.include_router(export_router)

    @application.get("/")
    def root():
        body = {
            "message": f"Bem-vindo à API do {settings.PROJECT_NAME}",
            "health": "/health/",
        }
        if not is_production:
            body["docs"] = "/docs"
        return body

    return application


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
