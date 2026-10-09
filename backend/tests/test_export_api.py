"""Export máquina-a-máquina (EXP-01..09): /api/v1/export/*.

Contrato: track-dash/.specs/features/vsl-por-anuncio/design.md, "Contrato publicado v1".
"""
import hashlib
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.video import Video, VideoAnalytics, VideoWatchSession
from app.models.viewer_attribution import ViewerAttribution

client = TestClient(app)

KEY = "chave-de-teste-do-export"
KEY_SHA256 = hashlib.sha256(KEY.encode()).hexdigest()
AUTH = {"X-Api-Key": KEY}

ROW_FIELDS = {
    "video_id", "session_id", "day", "external_id",
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "loaded", "played", "p25", "p50", "p75", "p100",
    "pitch_reached", "cta_reached", "clicked",
    "watched_seconds", "duration", "ranges", "updated_at",
}


def ts(day: int, hour: int, minute: int = 0, second: int = 0, micro: int = 0) -> datetime:
    return datetime(2030, 1, day, hour, minute, second, micro, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def export_key(monkeypatch):
    monkeypatch.setattr(settings, "EXPORT_API_KEY_SHA256", KEY_SHA256, raising=False)


@pytest.fixture(autouse=True)
def clean_viewer_tables():
    # O export varre todos os vídeos: cada teste começa sem eventos de outros testes
    db = SessionLocal()
    db.execute(text("DELETE FROM viewer_attribution"))
    db.execute(text("DELETE FROM video_watch_sessions"))
    db.execute(text("DELETE FROM video_analytics"))
    db.commit()
    db.close()


def make_video(**kw) -> str:
    db = SessionLocal()
    video = Video(title=kw.pop("title", "VSL"), video_url="https://x/v.mp4", **kw)
    db.add(video)
    db.commit()
    vid = video.id
    db.close()
    return vid


def add_event(video_id, session_id, event_type, at):
    db = SessionLocal()
    db.add(VideoAnalytics(video_id=video_id, session_id=session_id, event_type=event_type, created_at=at))
    db.commit()
    db.close()


def add_watch(video_id, session_id, day, ranges, watched, duration, updated_at):
    db = SessionLocal()
    db.add(VideoWatchSession(
        video_id=video_id, session_id=session_id, event_date=day, ranges=ranges,
        watched_seconds=watched, duration=duration, updated_at=updated_at,
    ))
    db.commit()
    db.close()


def add_attribution(video_id, session_id, **kw):
    db = SessionLocal()
    db.add(ViewerAttribution(video_id=video_id, session_id=session_id, **kw))
    db.commit()
    db.close()


def sessions(**params):
    params.setdefault("updated_since", "2030-01-01T00:00:00+00:00")
    return client.get("/api/v1/export/viewer-sessions", params=params, headers=AUTH)


# --- EXP-01 / EXP-02: auth -------------------------------------------------------

EXPORT_PATHS = [
    "/api/v1/export/ping",
    "/api/v1/export/videos",
    "/api/v1/export/viewer-sessions?updated_since=2030-01-01T00:00:00Z",
]


@pytest.mark.parametrize("path", EXPORT_PATHS)
@pytest.mark.parametrize("headers", [{}, {"X-Api-Key": "errada"}, {"X-Api-Key": KEY_SHA256}])
def test_sem_chave_ou_chave_errada_responde_401_sem_dados(path, headers):  # EXP-01
    make_video(title="segredo")
    res = client.get(path, headers=headers)

    assert res.status_code == 401
    body = res.json()
    assert set(body) == {"detail"}
    assert "segredo" not in res.text


def test_401_vem_antes_da_validacao_dos_parametros():
    res = client.get("/api/v1/export/viewer-sessions?limit=0")
    assert res.status_code == 401


@pytest.mark.parametrize("value", ["", "   "])
@pytest.mark.parametrize("path", EXPORT_PATHS)
def test_env_vazia_responde_404_em_tudo(monkeypatch, path, value):  # EXP-02
    monkeypatch.setattr(settings, "EXPORT_API_KEY_SHA256", value, raising=False)
    assert client.get(path, headers=AUTH).status_code == 404
    assert client.get(path).status_code == 404


def test_hash_em_maiusculas_na_env_tambem_vale(monkeypatch):
    monkeypatch.setattr(settings, "EXPORT_API_KEY_SHA256", KEY_SHA256.upper(), raising=False)
    assert client.get("/api/v1/export/ping", headers=AUTH).status_code == 200


# --- EXP-03 / EXP-04 -------------------------------------------------------------

def test_ping():  # EXP-03
    res = client.get("/api/v1/export/ping", headers=AUTH)
    assert res.status_code == 200
    assert res.json() == {"ok": True, "version": "1"}


def test_videos_com_pitch_e_cta():  # EXP-04
    full = make_video(
        title="VSL completa", duration=312.4,
        player_settings={"cta_time": 200, "cta_enabled": True, "pitch_delay": {"enabled": True, "time": 180}},
    )
    bare = make_video(title="VSL crua", duration=0.0, player_settings={})
    pitch_off = make_video(
        title="Pitch desligado", duration=60.0,
        player_settings={"cta_time": 0, "pitch_delay": {"enabled": False, "time": 30}},
    )

    res = client.get("/api/v1/export/videos", headers=AUTH)

    assert res.status_code == 200
    by_id = {v["id"]: v for v in res.json()["videos"]}
    assert by_id[full] == {
        "id": full, "name": "VSL completa", "duration_seconds": 312.4,
        "pitch_time_seconds": 180, "cta_time_seconds": 200,
    }
    assert by_id[bare] == {
        "id": bare, "name": "VSL crua", "duration_seconds": None,
        "pitch_time_seconds": None, "cta_time_seconds": None,
    }
    assert by_id[pitch_off]["pitch_time_seconds"] is None
    assert by_id[pitch_off]["cta_time_seconds"] is None


# --- EXP-05 / EXP-09: linhas e flags ----------------------------------------------

def test_linha_completa_com_flags_dos_eventos_e_tempo_do_watch():  # EXP-05
    vid = make_video(duration=312.4)
    add_event(vid, "s1", "impression", ts(2, 10, 0))
    add_event(vid, "s1", "play", ts(2, 10, 1))
    add_event(vid, "s1", "progress_25", ts(2, 10, 5))
    add_event(vid, "s1", "pitch_reached", ts(2, 10, 6))
    add_event(vid, "s1", "click", ts(2, 10, 7))
    add_watch(vid, "s1", date(2030, 1, 2), [[0, 41.5]], 41.5, 312.4, ts(2, 10, 10, 0, 123456))
    add_attribution(vid, "s1", external_id="abc123", utm_source="fb", utm_medium="paid",
                    utm_campaign="C|1", utm_content="Ad|120000000000000001", utm_term="S|2")

    res = sessions()

    assert res.status_code == 200
    body = res.json()
    assert body["next_cursor"] is None
    [row] = body["rows"]
    assert set(row) == ROW_FIELDS
    assert row == {
        "video_id": vid, "session_id": "s1", "day": "2030-01-02",
        "external_id": "abc123",
        "utm_source": "fb", "utm_medium": "paid", "utm_campaign": "C|1",
        "utm_content": "Ad|120000000000000001", "utm_term": "S|2",
        "loaded": True, "played": True, "p25": True, "p50": False, "p75": False, "p100": False,
        "pitch_reached": True, "cta_reached": False, "clicked": True,
        "watched_seconds": 41.5, "duration": 312.4, "ranges": [[0, 41.5]],
        "updated_at": "2030-01-02T10:10:00.123456+00:00",
    }


def test_uma_linha_por_dia_utc_e_updated_at_do_ultimo_evento():
    vid = make_video()
    add_event(vid, "s1", "impression", ts(2, 23, 59))
    add_event(vid, "s1", "play", ts(3, 0, 1))
    add_event(vid, "s1", "cta_reached", ts(3, 0, 30))

    rows = sessions().json()["rows"]

    assert [(r["day"], r["loaded"], r["played"], r["cta_reached"]) for r in rows] == [
        ("2030-01-02", True, False, False),
        ("2030-01-03", False, True, True),
    ]
    assert rows[1]["updated_at"] == "2030-01-03T00:30:00+00:00"
    # Sem linha no watch: 0, null, []
    assert (rows[0]["watched_seconds"], rows[0]["duration"], rows[0]["ranges"]) == (0, None, [])
    assert rows[0]["external_id"] is None and rows[0]["utm_source"] is None


def test_linha_so_com_watch_tem_flags_falsas():
    vid = make_video()
    add_watch(vid, "s9", date(2030, 1, 4), [[0, 10.0]], 10.0, 60.0, ts(4, 8))

    [row] = sessions().json()["rows"]

    assert row["day"] == "2030-01-04"
    assert not any(row[f] for f in ("loaded", "played", "p25", "p50", "p75", "p100", "pitch_reached", "cta_reached", "clicked"))
    assert row["updated_at"] == "2030-01-04T08:00:00+00:00"


def test_updated_at_e_o_maior_entre_evento_e_watch():
    vid = make_video()
    add_event(vid, "s1", "play", ts(2, 10))
    add_watch(vid, "s1", date(2030, 1, 2), [[0, 5.0]], 5.0, 60.0, ts(2, 9))

    [row] = sessions().json()["rows"]
    assert row["updated_at"] == "2030-01-02T10:00:00+00:00"


def test_eventos_sem_session_id_ficam_fora():
    vid = make_video()
    add_event(vid, None, "impression", ts(2, 10))
    add_event(vid, None, "play", ts(2, 10, 1))

    assert sessions().json()["rows"] == []


def test_so_volta_o_que_mudou_depois_de_updated_since_mas_com_o_dia_inteiro():
    vid = make_video()
    add_event(vid, "velha", "play", ts(2, 9))
    add_event(vid, "s1", "impression", ts(2, 9))
    add_event(vid, "s1", "play", ts(2, 11))

    rows = sessions(updated_since="2030-01-02T10:00:00Z").json()["rows"]

    assert [r["session_id"] for r in rows] == ["s1"]
    # A flag vem do dia inteiro, inclusive de evento anterior ao updated_since
    assert rows[0]["loaded"] is True and rows[0]["played"] is True


def test_updated_since_e_exclusivo():
    vid = make_video()
    add_event(vid, "s1", "play", ts(2, 10))
    assert sessions(updated_since="2030-01-02T10:00:00+00:00").json()["rows"] == []


def test_p100_vem_do_evento_e_nao_dos_ranges():  # EXP-09
    vid = make_video(duration=312.4)
    add_event(vid, "s1", "impression", ts(2, 10))
    add_event(vid, "s1", "play", ts(2, 10, 0, 5))
    add_watch(vid, "s1", date(2030, 1, 2), [[0, 312.4]], 312.4, 312.4, ts(2, 10, 6))

    [row] = sessions().json()["rows"]

    assert row["watched_seconds"] == 312.4
    assert row["ranges"] == [[0, 312.4]]
    assert row["p25"] is False and row["p50"] is False and row["p75"] is False and row["p100"] is False
    assert row["pitch_reached"] is False and row["cta_reached"] is False


# --- EXP-06 / EXP-07 / EXP-08: paginação -----------------------------------------

def _seed_five_rows():
    a = make_video()
    b = make_video()
    add_event(a, "s1", "play", ts(2, 10))
    add_event(b, "s2", "play", ts(2, 11))
    add_event(a, "s3", "play", ts(2, 12))
    # Empate de updated_at: desempata por video_id, session_id, day
    add_event(a, "s4", "play", ts(2, 13))
    add_event(a, "s5", "play", ts(2, 13))


def _sort_key(r):
    return (r["updated_at"], r["video_id"], r["session_id"], r["day"])


def test_ordem_por_updated_at_video_session_day():  # EXP-06
    _seed_five_rows()
    rows = sessions().json()["rows"]
    assert len(rows) == 5
    assert rows == sorted(rows, key=_sort_key)


def test_paginacao_com_limit_1_nao_repete_nem_pula():  # EXP-06 / EXP-07
    _seed_five_rows()
    full = sessions(limit=1000).json()["rows"]

    pages, cursor = [], None
    for _ in range(10):
        params = {"limit": 1}
        if cursor:
            params["cursor"] = cursor
        res = sessions(**params)
        assert res.status_code == 200
        body = res.json()
        assert len(body["rows"]) <= 1
        pages.extend(body["rows"])
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert pages == full
    assert len({_sort_key(r) for r in pages}) == 5


def test_next_cursor_so_quando_ha_mais_linhas():  # EXP-06
    _seed_five_rows()
    assert sessions(limit=5).json()["next_cursor"] is None
    page = sessions(limit=4).json()
    assert len(page["rows"]) == 4 and page["next_cursor"]
    rest = sessions(limit=4, cursor=page["next_cursor"]).json()
    assert len(rest["rows"]) == 1 and rest["next_cursor"] is None


def test_linha_alterada_depois_do_cursor_reaparece_adiante():  # EXP-07 (sem pular)
    _seed_five_rows()
    first = sessions(limit=2).json()
    vid = first["rows"][0]["video_id"]
    add_event(vid, first["rows"][0]["session_id"], "click", ts(2, 14))

    rest = sessions(limit=100, cursor=first["next_cursor"]).json()["rows"]
    last = rest[-1]
    assert (last["session_id"], last["clicked"]) == (first["rows"][0]["session_id"], True)


@pytest.mark.parametrize("limit", [0, -1, 1001])
def test_limit_fora_da_faixa_responde_422(limit):  # EXP-08
    assert sessions(limit=limit).status_code == 422


def test_limit_padrao_e_500():
    vid = make_video()
    db = SessionLocal()
    db.add_all([
        VideoAnalytics(video_id=vid, session_id=f"s{i:04d}", event_type="impression", created_at=ts(2, 10))
        for i in range(501)
    ])
    db.commit()
    db.close()

    body = sessions().json()
    assert len(body["rows"]) == 500 and body["next_cursor"]


@pytest.mark.parametrize("value", [None, "", "ontem", "2030-13-01"])
def test_updated_since_obrigatorio_e_valido(value):
    params = {} if value is None else {"updated_since": value}
    res = client.get("/api/v1/export/viewer-sessions", params=params, headers=AUTH)
    assert res.status_code == 422


@pytest.mark.parametrize("cursor", ["lixo", "eyJ4IjoxfQ", "!!!"])
def test_cursor_invalido_responde_422(cursor):
    assert sessions(cursor=cursor).status_code == 422


# --- contrato publicado -----------------------------------------------------------

def test_contrato_export_v1_bate_com_as_linhas():
    from pathlib import Path
    import json

    candidates = [
        Path("/contracts/export-v1.json"),
        Path(__file__).resolve().parent.parent.parent / "contracts" / "export-v1.json",
    ]
    path = next((p for p in candidates if p.exists()), None)
    assert path is not None, "contracts/export-v1.json não encontrado"
    contract = json.loads(path.read_text())
    assert set(contract["export"]["endpoints"]["GET /viewer-sessions"]["row_fields"]) == ROW_FIELDS
    assert contract["version"] == "1"
