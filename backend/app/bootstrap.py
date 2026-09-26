"""Preparação do banco no boot do container: `python -m app.bootstrap`.

Roda uma vez por container, antes do uvicorn subir os workers. Assim migrations e
a conta de Super Admin não disputam entre si os 4 workers do uvicorn.
"""
import logging

from app.core.config import assert_production_ready, settings
from app.core.migrations import run_migrations
from app.main import init_super_admin

logger = logging.getLogger("projetovturb.bootstrap")


def main() -> None:
    assert_production_ready(settings)
    run_migrations()
    init_super_admin()
    logger.info("Bootstrap concluído: schema no head e Super Admin sincronizado.")


if __name__ == "__main__":
    main()
