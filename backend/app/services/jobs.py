"""Fila de jobs no Postgres: enqueue na mesma transação do chamador, claim com SKIP LOCKED.

Várias réplicas do worker podem rodar: cada claim trava a linha escolhida e pula as
travadas pelos outros. Um job `running` sem heartbeat há mais de STALE_AFTER é de um
worker que morreu (OOM, deploy) e volta a ser pego.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, or_, update
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.job import Job

TRANSCODE_HLS = "transcode_hls"
DELETE_PREFIX = "delete_prefix"
KINDS = frozenset({TRANSCODE_HLS, DELETE_PREFIX})

STALE_AFTER = timedelta(minutes=10)
HEARTBEAT_EVERY = timedelta(minutes=1)
DEFAULT_MAX_ATTEMPTS = 3
MAX_ERROR_CHARS = 4000


def _now() -> datetime:
    return datetime.now(timezone.utc)


def backoff(attempt: int) -> timedelta:
    """1 min, 5 min, 25 min, ..."""
    return timedelta(minutes=5 ** max(0, attempt - 1))


def enqueue(
    db: Session,
    kind: str,
    payload: dict,
    *,
    now: Optional[datetime] = None,
    run_after: Optional[datetime] = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> Job:
    """Adiciona o job à transação do chamador (não faz commit): some junto num rollback."""
    if kind not in KINDS:
        raise ValueError(f"Tipo de job desconhecido: {kind}")
    now = now or _now()
    job = Job(kind=kind, payload=payload, status="queued", attempts=0, max_attempts=max_attempts,
              run_after=run_after or now, created_at=now, updated_at=now)
    db.add(job)
    db.flush()
    return job


def claim(db: Session, now: Optional[datetime] = None) -> Optional[Job]:
    """Pega o próximo job pronto (ou abandonado) e marca `running`. O commit é do chamador."""
    now = now or _now()
    job = (
        db.query(Job)
        .filter(
            or_(
                and_(Job.status == "queued", Job.run_after <= now),
                and_(Job.status == "running", Job.locked_at < now - STALE_AFTER),
            )
        )
        .order_by(Job.run_after, Job.id)
        .with_for_update(skip_locked=True)
        .first()
    )
    if job is None:
        return None
    job.status = "running"
    job.attempts += 1
    job.locked_at = now
    job.updated_at = now
    db.flush()
    return job


def heartbeat(job_id: int, now: Optional[datetime] = None) -> None:
    """Avisa que o job segue vivo. Sessão própria: roda durante um ffmpeg de horas."""
    with SessionLocal() as db:
        db.execute(update(Job).where(Job.id == job_id, Job.status == "running").values(locked_at=now or _now()))
        db.commit()


def complete(db: Session, job: Job, now: Optional[datetime] = None) -> None:
    job.status = "done"
    job.locked_at = None
    job.updated_at = now or _now()


def fail(db: Session, job: Job, error: str, now: Optional[datetime] = None) -> bool:
    """Registra a falha. Retorna True se foi a última tentativa (job `failed`)."""
    now = now or _now()
    job.last_error = (error or "erro desconhecido")[:MAX_ERROR_CHARS]
    job.locked_at = None
    job.updated_at = now
    if job.attempts >= job.max_attempts:
        job.status = "failed"
        return True
    job.status = "queued"
    job.run_after = now + backoff(job.attempts)
    return False


def release(db: Session, job: Job) -> None:
    """Devolve o job à fila sem gastar tentativa (worker recebeu SIGTERM no meio)."""
    job.status = "queued"
    job.attempts = max(0, job.attempts - 1)
    job.locked_at = None
    job.updated_at = _now()
