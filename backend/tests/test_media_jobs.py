"""Jobs de mídia rodando de ponta a ponta: transcode para HLS e limpeza de prefixo no storage."""
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.database import SessionLocal
from app.models.job import Job
from app.models.video import Video
from app.services import hls, jobs, media_jobs

HAS_FFMPEG = shutil.which("ffmpeg") is not None
PUBLIC = "https://video.exemplo.com/"


class FakeStorage:
    """Storage S3 de mentira em cima de um diretório."""

    def __init__(self, root: Path):
        self.root = root
        self.meta: dict[str, dict] = {}

    def public_url(self, key):
        return PUBLIC + key

    def key_from_public_url(self, url):
        return url.removeprefix(PUBLIC) if url and url.startswith(PUBLIC) else None

    def download_file(self, key, path):
        shutil.copyfile(self.root / key, path)

    def upload_path(self, path, key, content_type, cache_control):
        dest = self.root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
        self.meta[key] = {"content_type": content_type, "cache_control": cache_control}

    def delete_prefix(self, prefix):
        target = self.root / prefix
        if target.exists():
            shutil.rmtree(target)
        return 0

    def keys(self, prefix=""):
        return sorted(p.relative_to(self.root).as_posix() for p in (self.root / prefix).rglob("*") if p.is_file()) if (self.root / prefix).exists() else []


@pytest.fixture
def db():
    session = SessionLocal()
    session.query(Job).delete()
    session.commit()
    yield session
    session.close()


@pytest.fixture
def storage(tmp_path):
    return FakeStorage(tmp_path / "bucket")


def _source(storage: FakeStorage) -> str:
    key = f"videos/{uuid.uuid4()}/source.mp4"
    path = storage.root / key
    path.parent.mkdir(parents=True, exist_ok=True)
    if HAS_FFMPEG:
        subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=640x360:rate=25", "-t", "2",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
            check=True,
        )
    else:
        path.write_bytes(b"x")
    return key


def _video(db, storage_key, **kw):
    video = Video(title="VSL", video_url=PUBLIC + storage_key, storage_key=storage_key, status="processing", duration=0, **kw)
    db.add(video)
    db.commit()
    return video


def _enqueue_transcode(db, video):
    jobs.enqueue(db, media_jobs.TRANSCODE_HLS, {"video_id": video.id, "storage_key": video.storage_key})
    db.commit()


def _run(storage):
    return media_jobs.run_next_job(SessionLocal, storage)


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg ausente")
def test_transcode_publica_o_hls_e_marca_pronto(db, storage):
    key = _source(storage)
    video = _video(db, key)
    _enqueue_transcode(db, video)

    assert _run(storage) == "done"

    db.expire_all()
    video = db.get(Video, video.id)
    folder = key.rsplit("/", 1)[0]
    assert video.status == "ready" and video.processing_error is None
    assert video.hls_url.startswith(f"{PUBLIC}{folder}/hls/") and video.hls_url.endswith("/master.m3u8")
    assert video.duration == pytest.approx(2, abs=0.2)
    hls_prefix = storage.key_from_public_url(video.hls_url).rsplit("/", 1)[0] + "/"
    uploaded = storage.keys(hls_prefix)
    assert hls_prefix + "master.m3u8" in uploaded
    assert all(storage.meta[k]["cache_control"] == media_jobs.IMMUTABLE for k in uploaded)
    assert storage.meta[hls_prefix + "master.m3u8"]["content_type"] == "application/vnd.apple.mpegurl"


def test_fila_vazia_nao_faz_nada(db, storage):
    assert _run(storage) is None


def test_video_apagado_durante_o_transcode_nao_deixa_lixo(db, storage):
    key = _source(storage)
    video = _video(db, key)
    _enqueue_transcode(db, video)

    def fake_transcode(src, out_dir, **kw):
        # Enquanto o ffmpeg roda, alguém exclui o vídeo
        s = SessionLocal()
        s.delete(s.get(Video, video.id))
        s.commit()
        s.close()
        Path(out_dir).mkdir(parents=True)
        (Path(out_dir) / "master.m3u8").write_text("#EXTM3U")
        return hls.ProbeInfo(width=640, height=360, duration=2, has_audio=False)

    with patch.object(media_jobs.hls, "transcode", side_effect=fake_transcode):
        assert _run(storage) == "done"
    assert [k for k in storage.keys() if "/hls/" in k] == []


def test_video_trocado_durante_o_transcode_descarta_o_resultado(db, storage):
    key = _source(storage)
    video = _video(db, key)
    _enqueue_transcode(db, video)
    new_key = _source(storage)

    def fake_transcode(src, out_dir, **kw):
        s = SessionLocal()
        s.get(Video, video.id).storage_key = new_key
        s.commit()
        s.close()
        Path(out_dir).mkdir(parents=True)
        (Path(out_dir) / "master.m3u8").write_text("#EXTM3U")
        return hls.ProbeInfo(width=640, height=360, duration=2, has_audio=False)

    with patch.object(media_jobs.hls, "transcode", side_effect=fake_transcode):
        _run(storage)
    db.expire_all()
    assert db.get(Video, video.id).hls_url is None
    assert [k for k in storage.keys() if "/hls/" in k] == []


def test_hls_antigo_vai_para_a_fila_de_limpeza(db, storage):
    key = _source(storage)
    folder = key.rsplit("/", 1)[0]
    video = _video(db, key, hls_url=f"{PUBLIC}{folder}/hls/antigo/master.m3u8")
    _enqueue_transcode(db, video)

    def fake_transcode(src, out_dir, **kw):
        Path(out_dir).mkdir(parents=True)
        (Path(out_dir) / "master.m3u8").write_text("#EXTM3U")
        return hls.ProbeInfo(width=640, height=360, duration=2, has_audio=False)

    with patch.object(media_jobs.hls, "transcode", side_effect=fake_transcode):
        _run(storage)

    pending = db.query(Job).filter_by(kind=media_jobs.DELETE_PREFIX, status="queued").all()
    assert [j.payload["prefix"] for j in pending] == [f"{folder}/hls/antigo/"]


def test_falha_tenta_de_novo_e_depois_marca_o_video(db, storage):
    key = _source(storage)
    video = _video(db, key)
    jobs.enqueue(db, media_jobs.TRANSCODE_HLS, {"video_id": video.id, "storage_key": key}, max_attempts=2)
    db.commit()

    with patch.object(media_jobs.hls, "transcode", side_effect=hls.TranscodeError("arquivo corrompido")):
        assert _run(storage) == "retry"
        db.expire_all()
        assert db.get(Video, video.id).status == "processing"
        db.query(Job).update({Job.run_after: datetime.now(timezone.utc)})
        db.commit()
        assert _run(storage) == "failed"

    db.expire_all()
    video = db.get(Video, video.id)
    assert video.status == "failed"
    assert "arquivo corrompido" in video.processing_error
    assert video.hls_url is None


def test_erro_inesperado_nao_vaza_detalhe_interno_para_o_video(db, storage):
    key = _source(storage)
    video = _video(db, key)
    jobs.enqueue(db, media_jobs.TRANSCODE_HLS, {"video_id": video.id, "storage_key": key}, max_attempts=1)
    db.commit()

    with patch.object(media_jobs.hls, "transcode", side_effect=RuntimeError("/tmp/segredo senha=123")):
        assert _run(storage) == "failed"

    db.expire_all()
    assert "segredo" not in db.get(Video, video.id).processing_error
    assert "segredo" in db.query(Job).one().last_error


def test_parada_do_worker_devolve_o_job(db, storage):
    key = _source(storage)
    video = _video(db, key)
    _enqueue_transcode(db, video)

    with patch.object(media_jobs.hls, "transcode", side_effect=hls.TranscodeInterrupted()):
        assert _run(storage) == "released"

    job = db.query(Job).one()
    db.refresh(job)
    assert (job.status, job.attempts) == ("queued", 0)


def test_limpeza_de_prefixo(db, storage):
    key = _source(storage)
    folder = key.rsplit("/", 1)[0]
    (storage.root / folder / "hls" / "velho").mkdir(parents=True)
    (storage.root / folder / "hls" / "velho" / "master.m3u8").write_text("x")
    jobs.enqueue(db, media_jobs.DELETE_PREFIX, {"prefix": f"{folder}/hls/velho/"})
    db.commit()

    assert _run(storage) == "done"
    assert storage.keys(f"{folder}/hls/") == []
    assert storage.keys(folder) == [key]


@pytest.mark.parametrize("prefix", ["", "videos/", "../etc/", "thumbs/x/"])
def test_limpeza_recusa_prefixo_perigoso(db, storage, prefix):
    jobs.enqueue(db, media_jobs.DELETE_PREFIX, {"prefix": prefix}, max_attempts=1)
    db.commit()
    with patch.object(storage, "delete_prefix") as delete:
        assert _run(storage) == "failed"
    delete.assert_not_called()
