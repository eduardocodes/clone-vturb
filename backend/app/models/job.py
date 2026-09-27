"""Fila de jobs no Postgres (sem Redis), consumida pelo worker (`python -m app.worker`).

Protocolo (ver app/services/jobs.py):
- queued -> running: claim com SELECT ... FOR UPDATE SKIP LOCKED; attempts += 1.
- running -> done | queued (retry com backoff, run_after no futuro) | failed (sem tentativas).
- running parado sem heartbeat por mais de STALE_AFTER volta a ser pego por outro worker.
"""
from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, JSON, String, Text

from app.core.database import Base
from app.models.video import get_utc_now


class Job(Base):
    __tablename__ = "jobs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    kind = Column(String(40), nullable=False)
    payload = Column(JSON, nullable=False, default=dict)
    # queued | running | done | failed
    status = Column(String(20), nullable=False, default="queued", server_default="queued")
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    max_attempts = Column(Integer, nullable=False, default=3, server_default="3")
    run_after = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    __table_args__ = (
        # Busca do claim: próximos da fila e running abandonados
        Index("ix_jobs_status_run_after", "status", "run_after"),
    )
