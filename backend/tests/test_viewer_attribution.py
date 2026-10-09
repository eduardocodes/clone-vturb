"""Origem do espectador (VSL-01..05, VSL-08): POST /videos/{id}/attribution.

First-touch por (video_id, session_id): UTMs nunca são sobrescritas; o external_id
(xid) só é preenchido enquanto estiver nulo.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.database import SessionLocal
from app.core.rate_limit import limiter
from app.main import app
from app.models.video import Video
from app.models.viewer_attribution import ViewerAttribution

client = TestClient(app)

UTMS = {
    "utm_source": "fb",
    "utm_medium": "paid",
    "utm_campaign": "C|1",
    "utm_content": "Ad|120000000000000001",
    "utm_term": "S|2",
}


@pytest.fixture
def video_id():
    db = SessionLocal()
    video = Video(title="VSL origem", video_url="https://x/v.mp4", duration=120)
    db.add(video)
    db.commit()
    vid = video.id
    db.close()
    return vid


def _rows(video_id):
    db = SessionLocal()
    try:
        return db.query(ViewerAttribution).filter(ViewerAttribution.video_id == video_id).all()
    finally:
        db.close()


def _post(video_id, body, **kw):
    return client.post(f"/videos/{video_id}/attribution", json=body, **kw)


def test_grava_xid_e_as_cinco_utms(video_id):  # VSL-01
    res = _post(video_id, {"session_id": "vis_x", "xid": "abc123", **UTMS})

    assert res.status_code == 204
    assert res.content == b""
    [row] = _rows(video_id)
    assert row.session_id == "vis_x"
    assert row.external_id == "abc123"
    assert {k: getattr(row, k) for k in UTMS} == UTMS
    assert row.first_seen_at is not None


def test_segunda_chegada_mantem_as_utms_da_primeira(video_id):  # VSL-02
    assert _post(video_id, {"session_id": "vis_x", **UTMS}).status_code == 204
    other = {k: "outro" for k in UTMS}
    assert _post(video_id, {"session_id": "vis_x", **other}).status_code == 204

    [row] = _rows(video_id)
    assert {k: getattr(row, k) for k in UTMS} == UTMS


def test_xid_preenche_linha_com_external_id_nulo(video_id):  # VSL-03
    assert _post(video_id, {"session_id": "vis_x", **UTMS}).status_code == 204
    assert _post(video_id, {"session_id": "vis_x", "xid": "eid_tardio"}).status_code == 204

    [row] = _rows(video_id)
    assert row.external_id == "eid_tardio"
    assert row.utm_source == "fb"


def test_xid_nao_sobrescreve_external_id_existente(video_id):  # VSL-03 (first-touch)
    assert _post(video_id, {"session_id": "vis_x", "xid": "primeiro"}).status_code == 204
    assert _post(video_id, {"session_id": "vis_x", "xid": "segundo"}).status_code == 204

    [row] = _rows(video_id)
    assert row.external_id == "primeiro"


@pytest.mark.parametrize(
    "xid",
    ["a" * 101, "tem espaco", "ponto.e.virgula;", "acentuação", "", "x/y"],
)
def test_xid_invalido_responde_422_e_nao_grava(video_id, xid):  # VSL-04
    res = _post(video_id, {"session_id": "vis_x", "xid": xid, **UTMS})

    assert res.status_code == 422
    assert _rows(video_id) == []


def test_xid_no_limite_de_100_caracteres_e_aceito(video_id):
    xid = "A-z_9" * 20
    assert _post(video_id, {"session_id": "vis_x", "xid": xid}).status_code == 204
    assert _rows(video_id)[0].external_id == xid


def test_utm_longa_e_truncada_em_512(video_id):  # VSL-05
    longa = "c" * 2000
    assert _post(video_id, {"session_id": "vis_x", "utm_content": longa}).status_code == 204

    [row] = _rows(video_id)
    assert row.utm_content == "c" * 512


@pytest.mark.parametrize("body", [{}, {"session_id": ""}, {"session_id": "s" * 101}])
def test_session_id_obrigatorio_e_limitado(video_id, body):
    assert _post(video_id, {**body, **UTMS}).status_code == 422


def test_video_inexistente_responde_404():
    res = _post(str(uuid.uuid4()), {"session_id": "vis_x", "xid": "abc"})
    assert res.status_code == 404


def test_apagar_o_video_apaga_a_atribuicao(video_id):
    assert _post(video_id, {"session_id": "vis_x", "xid": "abc"}).status_code == 204
    db = SessionLocal()
    db.delete(db.get(Video, video_id))
    db.commit()
    db.close()
    assert _rows(video_id) == []


@pytest.fixture
def rate_limit_on():
    limiter.reset()
    limiter.enabled = True
    yield
    limiter.enabled = False
    limiter.reset()


def test_bloqueia_ip_depois_de_120_por_minuto(video_id, rate_limit_on):  # VSL-08
    headers = {"CF-Connecting-IP": "203.0.113.50"}
    body = {"session_id": "vis_x", "xid": "abc"}
    for _ in range(120):
        assert _post(video_id, body, headers=headers).status_code == 204
    blocked = _post(video_id, body, headers=headers)
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0
    # Outro IP segue livre
    assert _post(video_id, body, headers={"CF-Connecting-IP": "203.0.113.51"}).status_code == 204
