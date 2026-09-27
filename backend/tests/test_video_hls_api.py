"""API de vídeos com HLS ligado: enfileira o transcode, expõe status/hls_url e reprocessa na troca."""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api import videos
from app.api.deps import get_current_user
from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.job import Job
from app.models.user import User
from app.models.video import Video
from app.services import media_jobs

client = TestClient(app)
PUBLIC = "https://video.exemplo.com/"


def _key():
    return f"videos/{uuid.uuid4()}/source.mp4"


@pytest.fixture
def storage():
    fake = MagicMock()
    fake.public_url.side_effect = lambda key: PUBLIC + key
    fake.key_from_public_url.side_effect = lambda url: url.removeprefix(PUBLIC) if url and url.startswith(PUBLIC) else None
    with patch.object(videos, "storage_service", fake):
        yield fake


@pytest.fixture(autouse=True)
def logged():
    app.dependency_overrides[get_current_user] = lambda: User(id="u1", email="u@x.com")
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def clean_jobs():
    db = SessionLocal()
    db.query(Job).delete()
    db.commit()
    db.close()


@pytest.fixture
def hls_on():
    with patch.object(settings, "HLS_ENABLED", True):
        yield


def _jobs(kind=media_jobs.TRANSCODE_HLS):
    db = SessionLocal()
    try:
        return [(j.payload, j.status) for j in db.query(Job).filter_by(kind=kind).order_by(Job.id).all()]
    finally:
        db.close()


def _create(storage_key=None, video_url="https://cdn.externa.com/v.mp4"):
    body = {"title": "VSL", "video_url": video_url}
    if storage_key:
        body.update(storage_key=storage_key, source_size_bytes=10)
    res = client.post("/videos/", json=body)
    assert res.status_code == 201, res.text
    return res.json()


def test_video_do_storage_entra_em_processamento(storage, hls_on):
    key = _key()
    body = _create(key)
    assert body["status"] == "processing"
    assert body["hls_url"] is None
    assert _jobs() == [({"video_id": body["id"], "storage_key": key}, "queued")]


def test_url_externa_nao_passa_por_hls(storage, hls_on):
    body = _create()
    assert body["status"] == "ready"
    assert _jobs() == []


def test_hls_desligado_nao_enfileira(storage):
    body = _create(_key())
    assert body["status"] == "ready"
    assert _jobs() == []


def test_troca_do_video_reprocessa_e_esquece_o_hls_antigo(storage, hls_on):
    body = _create(_key())
    db = SessionLocal()
    db.query(Video).filter_by(id=body["id"]).update({"status": "ready", "hls_url": PUBLIC + "videos/x/hls/1/master.m3u8"})
    db.commit()
    db.close()

    new_key = _key()
    res = client.put(f"/videos/{body['id']}", json={"storage_key": new_key, "source_size_bytes": 20})

    assert res.json()["status"] == "processing"
    assert res.json()["hls_url"] is None
    assert _jobs()[-1] == ({"video_id": body["id"], "storage_key": new_key}, "queued")


def test_mesma_chave_nao_reprocessa(storage, hls_on):
    key = _key()
    body = _create(key)
    client.put(f"/videos/{body['id']}", json={"storage_key": key, "source_size_bytes": 10, "title": "Novo"})
    assert len(_jobs()) == 1


def test_trocar_por_url_externa_volta_para_pronto(storage, hls_on):
    body = _create(_key())
    res = client.put(f"/videos/{body['id']}", json={"video_url": "https://cdn.externa.com/outro.mp4"})
    assert res.json()["status"] == "ready"
    assert res.json()["hls_url"] is None
    assert res.json()["processing_error"] is None


def test_reprocessar_video_que_falhou(storage, hls_on):
    key = _key()
    body = _create(key)
    db = SessionLocal()
    db.query(Video).filter_by(id=body["id"]).update({"status": "failed", "processing_error": "falhou"})
    db.commit()
    db.close()

    res = client.post(f"/videos/{body['id']}/reprocess")

    assert res.status_code == 202
    assert res.json()["status"] == "processing"
    assert res.json()["processing_error"] is None
    assert len(_jobs()) == 2


def test_reprocessar_url_externa_e_recusado(storage, hls_on):
    body = _create()
    assert client.post(f"/videos/{body['id']}/reprocess").status_code == 400


def test_reprocessar_exige_login(storage, hls_on):
    body = _create(_key())
    app.dependency_overrides.pop(get_current_user, None)
    assert client.post(f"/videos/{body['id']}/reprocess").status_code == 401


def test_endpoint_publico_entrega_hls_sem_expor_a_chave(storage, hls_on):
    body = _create(_key())
    app.dependency_overrides.pop(get_current_user, None)
    public = client.get(f"/videos/{body['id']}").json()
    assert "hls_url" in public
    assert "storage_key" not in public


def test_falha_ao_apagar_do_storage_vira_job_de_limpeza(storage, hls_on):
    key = _key()
    body = _create(key)
    storage.delete_prefix.side_effect = RuntimeError("storage fora do ar")

    assert client.delete(f"/videos/{body['id']}").status_code == 204

    assert _jobs(media_jobs.DELETE_PREFIX) == [({"prefix": key.rsplit("/", 1)[0] + "/"}, "queued")]


def test_listagem_traz_o_status_do_processamento(storage, hls_on):
    body = _create(_key())
    db = SessionLocal()
    db.query(Video).filter_by(id=body["id"]).update({"status": "failed", "processing_error": "Arquivo corrompido", "hls_url": None})
    db.commit()
    db.close()

    row = next(v for v in client.get("/videos/").json() if v["id"] == body["id"])

    assert (row["status"], row["processing_error"], row["hls_url"]) == ("failed", "Arquivo corrompido", None)
