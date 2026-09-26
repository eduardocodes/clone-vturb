"""Processo de fundo: `python -m app.worker`.

Hoje: consolida as métricas (rollups) e limpa o bruto antigo a cada
WORKER_MAINTENANCE_INTERVAL segundos. Com mais de uma réplica, um
pg_try_advisory_lock garante que só uma consolida por vez.
"""
import logging
import os
import signal
import threading
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import text

from app.core.database import SessionLocal
from app.services import metrics_rollup

logger = logging.getLogger("projetovturb.worker")
logging.basicConfig(level=logging.INFO)

MAINTENANCE_LOCK_ID = 740_120_260_2
MAINTENANCE_INTERVAL = int(os.getenv("WORKER_MAINTENANCE_INTERVAL", "300"))
RAW_RETENTION_DAYS = int(os.getenv("RAW_RETENTION_DAYS", str(metrics_rollup.DEFAULT_KEEP_DAYS)))


class StopFlag(threading.Event):
    """Sinaliza parada (SIGTERM/SIGINT) e acorda o sleep do loop."""


def run_maintenance(session_factory=SessionLocal) -> bool:
    """Um ciclo de consolidação. Retorna True se rodou até o fim."""
    db = session_factory()
    try:
        got_lock = db.execute(text("SELECT pg_try_advisory_lock(:id)"), {"id": MAINTENANCE_LOCK_ID}).scalar()
        if not got_lock:
            logger.info("Outra réplica está consolidando; pulando este ciclo.")
            return False
        try:
            metrics_rollup.run_all(db, now=datetime.now(timezone.utc), keep_days=RAW_RETENTION_DAYS)
            return True
        except Exception:
            db.rollback()
            logger.exception("Falha ao consolidar métricas; tenta de novo no próximo ciclo.")
            return False
        finally:
            db.execute(text("SELECT pg_advisory_unlock(:id)"), {"id": MAINTENANCE_LOCK_ID})
            db.commit()
    finally:
        db.close()


def loop(tick: Callable[[], object], stop: StopFlag, interval: float) -> None:
    while not stop.is_set():
        tick()
        stop.wait(interval)


def main() -> None:
    stop = StopFlag()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    logger.info("Worker iniciado (manutenção a cada %ss).", MAINTENANCE_INTERVAL)
    loop(run_maintenance, stop, MAINTENANCE_INTERVAL)
    logger.info("Worker encerrado.")


if __name__ == "__main__":
    main()
