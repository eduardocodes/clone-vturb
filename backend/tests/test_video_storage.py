"""Vídeo vinculado a um objeto do storage: URL derivada da chave e limpeza ao excluir/trocar."""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api import videos
from app.api.deps import get_current_user
from app.main import app
from app.models.user import User

client = TestClient(app)


def _key():
    return f"videos/{uuid.uuid4()}/source.mp4"


@pytest.fixture
def storage():
    fake = MagicMock()
    fake.public_url.side_effect = lambda key: f"https://video.exemplo.com/{key}"
    fake.key_from_public_url.side_effect = lambda url: (
        url.removeprefix("https://video.exemplo.com/") if url and url.startswith("https://video.exemplo.com/") else None
    )
    with patch.object(videos, "storage_service", fake):
        yield fake


@pytest.fixture(autouse=True)
def logged():
    app.dependency_overrides[get_current_user] = lambda: User(id="u1", email="u@x.com")
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _create(storage_key=None, **extra):
    body = {"title": "VSL", "video_url": "https://qualquer/ignorada.mp4"}
    if storage_key:
        body["storage_key"] = storage_key
    body.update(extra)
    return client.post("/videos/", json=body)


def test_criar_com_storage_key_deriva_a_url_publica(storage):
    key = _key()
    res = _create(storage_key=key, source_size_bytes=123)
    assert res.status_code == 201
    body = res.json()
    assert body["video_url"] == f"https://video.exemplo.com/{key}"
    assert body["status"] == "ready"


def test_resposta_publica_nao_expoe_a_chave_do_storage(storage):
    video_id = _create(storage_key=_key()).json()["id"]
    app.dependency_overrides.pop(get_current_user, None)
    body = client.get(f"/videos/{video_id}").json()
    assert "storage_key" not in body
    assert "source_size_bytes" not in body


@pytest.mark.parametrize("bad_key", ["thumbs/x.jpg", "videos/../x/source.mp4", "outra/coisa.mp4"])
def test_criar_com_chave_invalida_e_recusado(storage, bad_key):
    assert _create(storage_key=bad_key).status_code == 422


def test_criar_com_url_externa_continua_funcionando(storage):
    res = _create(video_url="https://cdn.externa.com/vsl.mp4")
    assert res.status_code == 201
    assert res.json()["video_url"] == "https://cdn.externa.com/vsl.mp4"


def test_excluir_apaga_a_pasta_do_video_e_a_capa(storage):
    key = _key()
    thumb = f"https://video.exemplo.com/thumbs/{uuid.uuid4()}.jpg"
    video_id = _create(storage_key=key, thumbnail_url=thumb).json()["id"]

    assert client.delete(f"/videos/{video_id}").status_code == 204

    storage.delete_prefix.assert_called_once_with(key.rsplit("/", 1)[0] + "/")
    storage.delete_object.assert_called_once_with(thumb.removeprefix("https://video.exemplo.com/"))


def test_falha_no_storage_nao_impede_excluir(storage):
    storage.delete_prefix.side_effect = RuntimeError("s3 fora")
    video_id = _create(storage_key=_key()).json()["id"]
    assert client.delete(f"/videos/{video_id}").status_code == 204
    assert client.get(f"/videos/{video_id}").status_code == 404


def test_exclusao_em_massa_limpa_o_storage(storage):
    ids = [_create(storage_key=_key()).json()["id"] for _ in range(2)]
    res = client.post("/videos/bulk-delete", json={"video_ids": ids})
    assert res.json()["deleted_count"] == 2
    assert storage.delete_prefix.call_count == 2


def test_trocar_o_video_apaga_o_objeto_antigo(storage):
    old_key, new_key = _key(), _key()
    video_id = _create(storage_key=old_key).json()["id"]

    res = client.put(f"/videos/{video_id}", json={"storage_key": new_key, "source_size_bytes": 9})

    assert res.json()["video_url"] == f"https://video.exemplo.com/{new_key}"
    storage.delete_prefix.assert_called_once_with(old_key.rsplit("/", 1)[0] + "/")


def test_trocar_para_url_externa_limpa_a_chave(storage):
    old_key = _key()
    video_id = _create(storage_key=old_key).json()["id"]

    client.put(f"/videos/{video_id}", json={"video_url": "https://cdn.externa.com/nova.mp4"})

    storage.delete_prefix.assert_called_once_with(old_key.rsplit("/", 1)[0] + "/")
