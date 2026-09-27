"""Fila de jobs no Postgres: claim com SKIP LOCKED, retry com backoff e reclaim de job abandonado."""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.database import SessionLocal
from app.models.job import Job
from app.services import jobs

UTC = timezone.utc
NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)


@pytest.fixture
def db():
    session = SessionLocal()
    session.query(Job).delete()
    session.commit()
    yield session
    session.rollback()
    session.close()


def _enqueue(db, kind="delete_prefix", payload=None, **kw):
    job = jobs.enqueue(db, kind, payload or {"prefix": "videos/x/hls/1/"}, now=kw.pop("now", NOW), **kw)
    db.commit()
    return job


def test_enqueue_e_claim(db):
    job = _enqueue(db)
    claimed = jobs.claim(db, now=NOW)
    db.commit()
    assert claimed.id == job.id
    assert (claimed.status, claimed.attempts, claimed.locked_at) == ("running", 1, NOW)


def test_fila_vazia(db):
    assert jobs.claim(db, now=NOW) is None


def test_job_agendado_para_depois_nao_e_pego(db):
    _enqueue(db, run_after=NOW + timedelta(minutes=5))
    assert jobs.claim(db, now=NOW) is None
    assert jobs.claim(db, now=NOW + timedelta(minutes=6)) is not None


def test_dois_workers_nunca_pegam_o_mesmo_job(db):
    first, second = _enqueue(db), _enqueue(db)
    other = SessionLocal()
    try:
        a = jobs.claim(db, now=NOW)          # transação aberta, linha travada
        b = jobs.claim(other, now=NOW)       # SKIP LOCKED pula a linha de A
        assert {a.id, b.id} == {first.id, second.id}
        assert jobs.claim(other, now=NOW) is None  # nada sobrando
    finally:
        other.rollback()
        other.close()


def test_falha_volta_para_a_fila_com_backoff(db):
    _enqueue(db)
    job = jobs.claim(db, now=NOW)
    jobs.fail(db, job, "boom", now=NOW)
    db.commit()
    assert job.status == "queued"
    assert job.last_error == "boom"
    assert job.run_after == NOW + jobs.backoff(1)
    assert jobs.claim(db, now=NOW) is None


def test_backoff_cresce(db):
    assert jobs.backoff(1) < jobs.backoff(2) < jobs.backoff(3)


def test_ultima_tentativa_marca_como_falho(db):
    _enqueue(db, max_attempts=2)
    at = NOW
    for _ in range(2):
        job = jobs.claim(db, now=at)
        final = jobs.fail(db, job, "boom", now=at)
        db.commit()
        at = job.run_after or at
    assert final is True
    assert job.status == "failed"
    assert jobs.claim(db, now=at + timedelta(days=1)) is None


def test_erro_gigante_e_truncado(db):
    _enqueue(db)
    job = jobs.claim(db, now=NOW)
    jobs.fail(db, job, "x" * 50_000, now=NOW)
    assert len(job.last_error) <= jobs.MAX_ERROR_CHARS


def test_job_concluido(db):
    _enqueue(db)
    job = jobs.claim(db, now=NOW)
    jobs.complete(db, job, now=NOW)
    db.commit()
    assert job.status == "done"
    assert jobs.claim(db, now=NOW + timedelta(days=1)) is None


def test_job_abandonado_volta_para_a_fila(db):
    _enqueue(db)
    jobs.claim(db, now=NOW)
    db.commit()
    # Worker morreu sem heartbeat: depois do prazo outro worker pega de novo
    assert jobs.claim(db, now=NOW + jobs.STALE_AFTER - timedelta(seconds=1)) is None
    again = jobs.claim(db, now=NOW + jobs.STALE_AFTER + timedelta(seconds=1))
    assert again is not None and again.attempts == 2


def test_heartbeat_segura_o_job(db):
    _enqueue(db)
    job = jobs.claim(db, now=NOW)
    db.commit()
    later = NOW + jobs.STALE_AFTER
    jobs.heartbeat(job.id, now=later)
    assert jobs.claim(db, now=later + timedelta(seconds=30)) is None


def test_interrompido_volta_sem_gastar_tentativa(db):
    _enqueue(db)
    job = jobs.claim(db, now=NOW)
    jobs.release(db, job)
    db.commit()
    assert (job.status, job.attempts, job.locked_at) == ("queued", 0, None)
    assert jobs.claim(db, now=NOW) is not None


def test_tipo_desconhecido_e_recusado(db):
    with pytest.raises(ValueError):
        jobs.enqueue(db, "rm_rf", {}, now=NOW)
