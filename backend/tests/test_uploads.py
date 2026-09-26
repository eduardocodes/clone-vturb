"""Upload direto do navegador para o storage (URLs assinadas), sem o arquivo passar pelo backend."""
import re
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api import uploads
from app.api.deps import get_current_user
from app.core.config import settings
from app.main import app
from app.models.user import User

client = TestClient(app)
KEY_RE = re.compile(r"^videos/[0-9a-f-]{36}/source\.mp4$")
MB = 1024 * 1024


@pytest.fixture
def storage():
    fake = MagicMock()
    fake.is_configured.return_value = True
    fake.create_multipart_upload.return_value = "up-1"
    fake.presign_upload_part.side_effect = lambda key, upload_id, n: f"https://s3/{key}?part={n}"
    fake.presign_put.return_value = "https://s3/put"
    fake.public_url.side_effect = lambda key: f"https://video.exemplo.com/{key}"
    with patch.object(uploads, "storage_service", fake):
        yield fake


@pytest.fixture
def logged():
    app.dependency_overrides[get_current_user] = lambda: User(id="u1", email="u@x.com")
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _init_video(size=100 * MB, **overrides):
    body = {"kind": "video", "filename": "vsl.mp4", "content_type": "video/mp4", "size": size}
    body.update(overrides)
    return client.post("/uploads/init", json=body)


def test_rotas_exigem_login(storage):
    assert client.get("/uploads/config").status_code == 401
    assert _init_video().status_code == 401


def test_config_informa_se_o_upload_direto_esta_disponivel(storage, logged):
    body = client.get("/uploads/config").json()
    assert body["direct"] is True
    assert body["max_video_bytes"] == settings.MAX_VIDEO_BYTES
    storage.is_configured.return_value = False
    assert client.get("/uploads/config").json()["direct"] is False


def test_init_de_video_cria_multipart_com_chave_propria(storage, logged):
    res = _init_video(size=100 * MB)
    assert res.status_code == 200
    body = res.json()
    assert KEY_RE.match(body["key"])
    assert body["method"] == "multipart"
    assert body["upload_id"] == "up-1"
    assert body["part_size"] == settings.UPLOAD_PART_SIZE
    assert body["part_count"] == -(-100 * MB // settings.UPLOAD_PART_SIZE)
    storage.create_multipart_upload.assert_called_once_with(body["key"], "video/mp4")


def test_init_aumenta_a_parte_para_nao_passar_de_10000_partes(storage, logged):
    with patch.object(settings, "MAX_VIDEO_BYTES", 10**12):
        body = _init_video(size=200_000 * MB).json()
    assert body["part_count"] <= 10_000
    assert body["part_size"] * body["part_count"] >= 200_000 * MB


def test_init_de_thumbnail_devolve_put_assinado_e_url_publica(storage, logged):
    res = client.post("/uploads/init", json={
        "kind": "thumbnail", "filename": "capa.JPG", "content_type": "image/jpeg", "size": 200_000,
    })
    body = res.json()
    assert res.status_code == 200
    assert body["method"] == "put"
    assert re.match(r"^thumbs/[0-9a-f-]{36}\.jpg$", body["key"])
    assert body["url"] == "https://s3/put"
    assert body["headers"] == {"Content-Type": "image/jpeg"}
    assert body["public_url"] == f"https://video.exemplo.com/{body['key']}"


@pytest.mark.parametrize(
    "overrides",
    [
        {"filename": "vsl.svg", "content_type": "image/svg+xml"},
        {"filename": "vsl.mp4", "content_type": "text/html"},
        {"filename": "vsl.exe", "content_type": "video/mp4"},
        {"kind": "thumbnail", "filename": "capa.mp4", "content_type": "video/mp4"},
        {"size": 0},
    ],
)
def test_init_recusa_arquivo_invalido(storage, logged, overrides):
    assert _init_video(**overrides).status_code == 400
    storage.create_multipart_upload.assert_not_called()


def test_init_recusa_arquivo_grande_demais(storage, logged):
    assert _init_video(size=settings.MAX_VIDEO_BYTES + 1).status_code == 413


def test_sem_storage_configurado_responde_503(storage, logged):
    storage.is_configured.return_value = False
    assert _init_video().status_code == 503


def test_assinar_partes_em_lote(storage, logged):
    key = _init_video().json()["key"]
    res = client.post("/uploads/sign-parts", json={"key": key, "upload_id": "up-1", "part_numbers": [1, 2, 3]})
    assert res.status_code == 200
    assert res.json()["urls"] == {str(n): f"https://s3/{key}?part={n}" for n in (1, 2, 3)}


@pytest.mark.parametrize(
    "key, parts",
    [
        ("thumbs/../../segredo.mp4", [1]),
        ("videos/qualquer/source.mp4", [1]),
        ("VALID", [0]),
        ("VALID", [10_001]),
        ("VALID", list(range(1, 102))),
    ],
)
def test_assinar_partes_valida_chave_e_numeros(storage, logged, key, parts):
    if key == "VALID":
        key = _init_video().json()["key"]
    res = client.post("/uploads/sign-parts", json={"key": key, "upload_id": "up-1", "part_numbers": parts})
    assert res.status_code in (400, 422)


def test_complete_confere_tamanho_e_devolve_url_publica(storage, logged):
    key = _init_video().json()["key"]
    storage.head.return_value = {"size": 100 * MB, "content_type": "video/mp4"}

    res = client.post("/uploads/complete", json={
        "key": key, "upload_id": "up-1", "size": 100 * MB,
        "parts": [{"part_number": 2, "etag": '"b"'}, {"part_number": 1, "etag": '"a"'}],
    })

    assert res.status_code == 200
    assert res.json() == {"key": key, "url": f"https://video.exemplo.com/{key}", "size": 100 * MB}
    storage.complete_multipart_upload.assert_called_once_with(key, "up-1", [(2, '"b"'), (1, '"a"')])


def test_complete_com_tamanho_divergente_apaga_e_recusa(storage, logged):
    key = _init_video().json()["key"]
    storage.head.return_value = {"size": 5, "content_type": "video/mp4"}

    res = client.post("/uploads/complete", json={
        "key": key, "upload_id": "up-1", "size": 100 * MB, "parts": [{"part_number": 1, "etag": '"a"'}],
    })

    assert res.status_code == 400
    storage.delete_object.assert_called_once_with(key)


def test_abort_cancela_o_multipart(storage, logged):
    key = _init_video().json()["key"]
    res = client.post("/uploads/abort", json={"key": key, "upload_id": "up-1"})
    assert res.status_code == 204
    storage.abort_multipart_upload.assert_called_once_with(key, "up-1")
