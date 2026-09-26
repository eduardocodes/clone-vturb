"""Ingestão de eventos do player: contrato, deduplicação e trechos assistidos (sendBeacon)."""
import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func

from app.core.database import SessionLocal
from app.main import app
from app.models.video import Video, VideoAnalytics, VideoWatchSession
from app.schemas.video import EVENT_TYPES

client = TestClient(app)

CONTRACT_CANDIDATES = [
    Path("/contracts/analytics-events.json"),
    Path(__file__).resolve().parent.parent.parent / "contracts" / "analytics-events.json",
]


@pytest.fixture
def video_id():
    db = SessionLocal()
    video = Video(title="VSL métricas", video_url="https://x/v.mp4", duration=120)
    db.add(video)
    db.commit()
    vid = video.id
    db.close()
    return vid


def _count(video_id, **filters):
    db = SessionLocal()
    try:
        q = db.query(func.count(VideoAnalytics.id)).filter(VideoAnalytics.video_id == video_id)
        for k, v in filters.items():
            q = q.filter(getattr(VideoAnalytics, k) == v)
        return q.scalar()
    finally:
        db.close()


def test_contrato_de_eventos_bate_com_o_front():
    path = next((p for p in CONTRACT_CANDIDATES if p.exists()), None)
    assert path is not None, "contracts/analytics-events.json não encontrado"
    assert sorted(json.loads(path.read_text())["event_types"]) == sorted(EVENT_TYPES)


@pytest.mark.parametrize(
    "body",
    [
        {"event_type": "hackeado"},
        {"event_type": "play", "session_id": "x" * 101},
        {"event_type": "progress_25", "watch_time_seconds": -1},
        {"event_type": "progress_25", "watch_time_seconds": 10**9},
    ],
)
def test_evento_invalido_e_recusado(video_id, body):
    assert client.post(f"/videos/{video_id}/events", json=body).status_code == 422


def test_referer_gigante_e_truncado(video_id):
    res = client.post(f"/videos/{video_id}/events", json={"event_type": "impression", "session_id": "s1", "referer": "https://x/" + "a" * 2000})
    assert res.status_code == 201
    db = SessionLocal()
    row = db.query(VideoAnalytics).filter(VideoAnalytics.video_id == video_id).one()
    db.close()
    assert len(row.referer) == 512


def test_play_repetido_em_rajada_conta_uma_vez(video_id):
    event_type = "play"
    body = {"event_type": event_type, "session_id": "sessao-1", "watch_time_seconds": 30}
    first = client.post(f"/videos/{video_id}/events", json=body)
    second = client.post(f"/videos/{video_id}/events", json=body)
    assert first.status_code == 201 and second.status_code == 201
    assert second.json()["status"] == "ignored_duplicate"
    assert _count(video_id, event_type=event_type) == 1


def test_impressao_repetida_conta_cada_carregamento(video_id):
    for _ in range(2):
        client.post(f"/videos/{video_id}/events", json={"event_type": "impression", "session_id": "s1"})
    assert _count(video_id, event_type="impression") == 2


def test_play_depois_da_janela_conta_de_novo(video_id):
    from datetime import datetime, timedelta, timezone

    db = SessionLocal()
    db.add(VideoAnalytics(
        video_id=video_id, event_type="play", session_id="s1",
        created_at=datetime.now(timezone.utc) - timedelta(seconds=30),
    ))
    db.commit()
    db.close()

    client.post(f"/videos/{video_id}/events", json={"event_type": "play", "session_id": "s1"})

    assert _count(video_id, event_type="play") == 2


def test_clique_nao_e_deduplicado(video_id):
    for _ in range(3):
        client.post(f"/videos/{video_id}/events", json={"event_type": "click", "session_id": "s1"})
    assert _count(video_id, event_type="click") == 3


def test_sessoes_diferentes_contam_separado(video_id):
    for sid in ("a", "b"):
        client.post(f"/videos/{video_id}/events", json={"event_type": "play", "session_id": sid})
    assert _count(video_id, event_type="play") == 2


def test_evento_de_video_inexistente_da_404():
    assert client.post(f"/videos/{uuid.uuid4()}/events", json={"event_type": "play"}).status_code == 404


# --- trechos assistidos ---------------------------------------------------------------

def _watch(video_id, payload, as_beacon=True):
    if as_beacon:
        # sendBeacon manda text/plain para não disparar preflight de CORS
        return client.post(f"/videos/{video_id}/watch", content=json.dumps(payload), headers={"Content-Type": "text/plain;charset=UTF-8"})
    return client.post(f"/videos/{video_id}/watch", json=payload)


def _session(video_id, session_id):
    db = SessionLocal()
    try:
        return db.query(VideoWatchSession).filter_by(video_id=video_id, session_id=session_id).one_or_none()
    finally:
        db.close()


def test_beacon_text_plain_grava_os_trechos(video_id):
    res = _watch(video_id, {"session_id": "s1", "duration": 120, "ranges": [[0, 10], [30, 40]]})
    assert res.status_code == 204
    row = _session(video_id, "s1")
    assert row.ranges == [[0, 10], [30, 40]]
    assert row.watched_seconds == pytest.approx(20)


def test_envios_seguidos_unem_os_trechos(video_id):
    _watch(video_id, {"session_id": "s1", "duration": 120, "ranges": [[0, 10]]})
    _watch(video_id, {"session_id": "s1", "duration": 120, "ranges": [[0, 25]]}, as_beacon=False)
    row = _session(video_id, "s1")
    assert row.ranges == [[0, 25]]
    assert row.watched_seconds == pytest.approx(25)


@pytest.mark.parametrize(
    "payload",
    [
        {"session_id": "s1", "duration": 120, "ranges": [[0, 1]] * 501},
        {"session_id": "", "duration": 120, "ranges": [[0, 1]]},
        {"session_id": "s1", "duration": -5, "ranges": [[0, 1]]},
        {"session_id": "s1", "duration": 120, "ranges": [[0]]},
    ],
)
def test_trechos_invalidos_sao_recusados(video_id, payload):
    assert _watch(video_id, payload).status_code == 422


def test_corpo_que_nao_e_json_e_recusado(video_id):
    res = client.post(f"/videos/{video_id}/watch", content="isso não é json", headers={"Content-Type": "text/plain"})
    assert res.status_code == 422


def test_trechos_de_video_inexistente_da_404():
    assert _watch(str(uuid.uuid4()), {"session_id": "s1", "duration": 10, "ranges": [[0, 1]]}).status_code == 404


def test_duracao_informada_pelo_player_preenche_video_sem_duracao():
    db = SessionLocal()
    video = Video(title="Sem duração", video_url="https://x/v.mp4", duration=0)
    db.add(video)
    db.commit()
    vid = video.id
    db.close()

    _watch(vid, {"session_id": "s1", "duration": 150.4, "ranges": [[0, 5]]})

    db = SessionLocal()
    assert db.get(Video, vid).duration == pytest.approx(150.4)
    db.close()


def test_duracao_do_player_nao_sobrescreve_duracao_conhecida(video_id):
    _watch(video_id, {"session_id": "s1", "duration": 999, "ranges": [[0, 5]]})
    db = SessionLocal()
    assert db.get(Video, video_id).duration == pytest.approx(120)
    db.close()
