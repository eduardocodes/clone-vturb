"""Processo de fundo: `python -m app.worker`.

- Jobs de mídia (fila `jobs` no Postgres): transcode para HLS e limpeza de storage,
  um por vez. Com a fila vazia, dorme WORKER_POLL_INTERVAL segundos.
- Manutenção a cada WORKER_MAINTENANCE_INTERVAL segundos: consolida as métricas
  (rollups) e limpa o bruto antigo. Com mais de uma réplica, um pg_try_advisory_lock
  garante que só uma consolida por vez; os jobs se dividem via SKIP LOCKED.
"""
import logging
import os
import signal
import threading
import time
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import text

from app.core.database import SessionLocal
from app.services import media_jobs, metrics_rollup

logger = logging.getLogger("projetovturb.worker")
logging.basicConfig(level=logging.INFO)

MAINTENANCE_LOCK_ID = 740_120_260_2
MAINTENANCE_INTERVAL = int(os.getenv("WORKER_MAINTENANCE_INTERVAL", "300"))
POLL_INTERVAL = float(os.getenv("WORKER_POLL_INTERVAL", "5"))
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


def make_tick(
    maintenance: Callable[[], object],
    next_job: Callable[[], object],
    maintenance_interval: float,
    clock: Callable[[], float] = time.monotonic,
) -> Callable[[], bool]:
    """Um passo do worker: manutenção quando vence o intervalo, depois um job da fila.
    Retorna True se rodou um job (o loop não dorme enquanto houver fila)."""
    next_maintenance = [clock()]

    def tick() -> bool:
        if clock() >= next_maintenance[0]:
            maintenance()
            next_maintenance[0] = clock() + maintenance_interval
        return next_job() is not None

    return tick


def loop(tick: Callable[[], object], stop: StopFlag, interval: float) -> None:
    while not stop.is_set():
        try:
            did_work = tick()
        except Exception:
            # Ex.: banco fora do ar. Espera e tenta de novo em vez de derrubar o container.
            logger.exception("Erro inesperado no worker; tentando de novo em %ss.", interval)
            did_work = False
        if not did_work:
            stop.wait(interval)


def main() -> None:
    stop = StopFlag()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    try:
        # Transcode é trabalho de fundo: cede CPU para a API quando dividem a máquina
        os.nice(10)
    except OSError:
        pass
    logger.info("Worker iniciado (jobs a cada %ss com a fila vazia, manutenção a cada %ss).", POLL_INTERVAL, MAINTENANCE_INTERVAL)
    tick = make_tick(
        maintenance=run_maintenance,
        next_job=lambda: media_jobs.run_next_job(should_stop=stop.is_set),
        maintenance_interval=MAINTENANCE_INTERVAL,
    )
    loop(tick, stop, POLL_INTERVAL)
    logger.info("Worker encerrado.")


if __name__ == "__main__":
    main()
