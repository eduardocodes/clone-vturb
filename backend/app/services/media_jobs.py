"""Execução dos jobs de mídia pelo worker: transcode para HLS e limpeza de prefixo no storage.

Cada job roda fora de transação longa: claim + commit, trabalho pesado (download, ffmpeg,
upload) sem segurar conexão, e no fim uma transação curta que confere se o vídeo ainda é
o mesmo antes de publicar o resultado.
"""
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional

from app.core.database import SessionLocal
from app.models.job import Job
from app.models.video import Video
from app.services import hls, jobs
from app.services.jobs import DELETE_PREFIX, TRANSCODE_HLS
from app.services.storage import storage_service

logger = logging.getLogger("projetovturb.media_jobs")

IMMUTABLE = "public, max-age=31536000, immutable"
HLS_THREADS = int(os.getenv("HLS_THREADS", "2"))
GENERIC_ERROR = "Falha inesperada no processamento. Tente reprocessar; se persistir, veja os logs do worker."
ABANDONED_ERROR = "O processamento foi interrompido várias vezes (o worker pode estar sem memória)."

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
# Só estes prefixos podem ser apagados por job: a pasta de um vídeo ou uma versão do HLS
VIDEO_FOLDER_RE = re.compile(rf"^videos/{_UUID}/$")
HLS_PREFIX_RE = re.compile(rf"^videos/{_UUID}/hls/[A-Za-z0-9_-]+/$")

__all__ = ["TRANSCODE_HLS", "DELETE_PREFIX", "IMMUTABLE", "run_next_job", "video_folder"]


def video_folder(storage_key: str) -> str:
    """videos/<uuid>/source.mp4 -> videos/<uuid>/"""
    return storage_key.rsplit("/", 1)[0] + "/"


def _prefix_of(key: str) -> str:
    return key.rsplit("/", 1)[0] + "/"


def _public_message(exc: Exception) -> str:
    return str(exc)[:500] if isinstance(exc, hls.TranscodeError) else GENERIC_ERROR


def _transcode(session_factory, storage, job_id: int, payload: dict, should_stop: Callable[[], bool]) -> None:
    video_id, key = payload["video_id"], payload["storage_key"]
    with session_factory() as db:
        video = db.get(Video, video_id)
        if video is None or video.storage_key != key:
            logger.info("Job %s: vídeo %s apagado ou trocado antes do transcode; nada a fazer.", job_id, video_id)
            return

    prefix = f"{video_folder(key)}hls/{job_id}/"
    last_beat = [time.monotonic()]

    def tick() -> None:
        if time.monotonic() - last_beat[0] >= jobs.HEARTBEAT_EVERY.total_seconds():
            jobs.heartbeat(job_id)
            last_beat[0] = time.monotonic()

    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="vturb-hls-") as tmp:
        src = os.path.join(tmp, "source" + Path(key).suffix)
        storage.download_file(key, src)
        out = os.path.join(tmp, "hls")
        info = hls.transcode(src, out, threads=HLS_THREADS, should_stop=should_stop, on_tick=tick)
        files = sorted(p for p in Path(out).rglob("*") if p.is_file())
        for path in files:
            if should_stop():
                raise hls.TranscodeInterrupted()
            rel = path.relative_to(out).as_posix()
            storage.upload_path(str(path), prefix + rel, hls.content_type_for(rel), IMMUTABLE)
            tick()

    with session_factory() as db:
        video = db.query(Video).filter(Video.id == video_id).with_for_update().first()
        if video is None or video.storage_key != key:
            db.rollback()
            logger.info("Job %s: vídeo %s apagado ou trocado durante o transcode; descartando %s.", job_id, video_id, prefix)
            storage.delete_prefix(prefix)
            return
        old_key = storage.key_from_public_url(video.hls_url) if video.hls_url else None
        video.hls_url = storage.public_url(prefix + "master.m3u8")
        video.status = "ready"
        video.processing_error = None
        if info.duration > 0:
            video.duration = info.duration
        if old_key and _prefix_of(old_key) != prefix and HLS_PREFIX_RE.match(_prefix_of(old_key)):
            jobs.enqueue(db, DELETE_PREFIX, {"prefix": _prefix_of(old_key)})
        db.commit()
    logger.info("Job %s: HLS de %s publicado (%s arquivos) em %.0fs.", job_id, video_id, len(files), time.monotonic() - started)


def _delete_prefix(session_factory, storage, job_id: int, payload: dict, should_stop: Callable[[], bool]) -> None:
    prefix = payload.get("prefix") or ""
    if not (VIDEO_FOLDER_RE.match(prefix) or HLS_PREFIX_RE.match(prefix)):
        raise ValueError(f"Prefixo recusado para limpeza: {prefix!r}")
    deleted = storage.delete_prefix(prefix)
    logger.info("Job %s: %s objetos apagados em %s.", job_id, deleted, prefix)


HANDLERS = {TRANSCODE_HLS: _transcode, DELETE_PREFIX: _delete_prefix}


def _record_failure(session_factory, job_id: int, kind: str, payload: dict, exc: Exception) -> str:
    with session_factory() as db:
        job = db.query(Job).filter(Job.id == job_id).with_for_update().one()
        final = jobs.fail(db, job, f"{type(exc).__name__}: {exc}")
        if final and kind == TRANSCODE_HLS:
            video = db.get(Video, payload.get("video_id"))
            if video is not None and video.storage_key == payload.get("storage_key"):
                video.status = "failed"
                video.processing_error = _public_message(exc)
        db.commit()
    return "failed" if final else "retry"


def run_next_job(
    session_factory=SessionLocal,
    storage=None,
    should_stop: Callable[[], bool] = lambda: False,
) -> Optional[str]:
    """Roda um job da fila. Retorna done | retry | failed | released, ou None com a fila vazia."""
    storage = storage or storage_service
    with session_factory() as db:
        job = jobs.claim(db)
        if job is None:
            db.commit()
            return None
        job_id, kind, payload = job.id, job.kind, dict(job.payload or {})
        abandoned = job.attempts > job.max_attempts
        db.commit()

    if abandoned:
        # Worker morreu no meio deste job mais vezes do que as tentativas permitem
        return _record_failure(session_factory, job_id, kind, payload, hls.TranscodeError(ABANDONED_ERROR))

    logger.info("Job %s (%s) iniciado.", job_id, kind)
    try:
        HANDLERS[kind](session_factory, storage, job_id, payload, should_stop)
    except hls.TranscodeInterrupted:
        with session_factory() as db:
            jobs.release(db, db.get(Job, job_id))
            db.commit()
        logger.info("Job %s devolvido à fila (worker parando).", job_id)
        return "released"
    except Exception as exc:
        logger.exception("Job %s (%s) falhou.", job_id, kind)
        return _record_failure(session_factory, job_id, kind, payload, exc)

    with session_factory() as db:
        jobs.complete(db, db.get(Job, job_id))
        db.commit()
    return "done"
