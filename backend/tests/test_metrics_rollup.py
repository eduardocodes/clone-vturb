"""Modelo de leitura das métricas: rollups por hora/dia com watermark + parte recente ao vivo."""
from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func

from app.api.deps import get_current_user
from app.core.database import SessionLocal
from app.main import app
from app.models.metrics import MetricsDaily, MetricsHourly, RetentionDaily, RollupState
from app.models.user import User
from app.models.video import Video, VideoAnalytics, VideoWatchSession
from app.services import metrics_rollup
from app.services.metrics_query import downsample_curve

client = TestClient(app)
UTC = timezone.utc


@pytest.fixture
def db():
    session = SessionLocal()
    # Estado de rollup é global: cada teste começa do zero
    session.query(RollupState).delete()
    session.query(MetricsHourly).delete()
    session.query(RetentionDaily).delete()
    session.query(MetricsDaily).delete()
    session.commit()
    yield session
    session.close()


@pytest.fixture
def video(db):
    v = Video(title="VSL rollup", video_url="https://x/v.mp4", duration=100)
    db.add(v)
    db.commit()
    return v


@pytest.fixture
def logged():
    app.dependency_overrides[get_current_user] = lambda: User(id="u1", email="u@x.com")
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _event(db, video_id, event_type, at, session_id=None):
    db.add(VideoAnalytics(
        video_id=video_id, event_type=event_type, session_id=session_id,
        created_at=at, watch_time_seconds=0,
    ))
    db.commit()


def _session(db, video_id, session_id, day, ranges):
    from app.services.watch_ranges import watched_seconds

    db.add(VideoWatchSession(
        video_id=video_id, session_id=session_id, event_date=day, ranges=ranges,
        watched_seconds=watched_seconds(ranges), duration=100, updated_at=datetime.now(UTC),
    ))
    db.commit()


def _hourly(db, video_id):
    return {r.hour_utc: r for r in db.query(MetricsHourly).filter_by(video_id=video_id).all()}


NOW = datetime(2026, 9, 26, 15, 30, tzinfo=UTC)


def test_rollup_por_hora_so_fecha_horas_encerradas(db, video):
    _event(db, video.id, "impression", NOW - timedelta(hours=3), "a")
    _event(db, video.id, "play", NOW - timedelta(hours=3), "a")
    _event(db, video.id, "impression", NOW - timedelta(minutes=10), "b")  # hora corrente

    metrics_rollup.roll_hourly(db, now=NOW)

    rows = _hourly(db, video.id)
    assert list(rows) == [datetime(2026, 9, 26, 12, tzinfo=UTC)]
    assert (rows[datetime(2026, 9, 26, 12, tzinfo=UTC)].impressions, rows[datetime(2026, 9, 26, 12, tzinfo=UTC)].plays) == (1, 1)
    assert metrics_rollup.watermark(db, "hourly") == datetime(2026, 9, 26, 15, tzinfo=UTC)


def test_rollup_por_hora_e_idempotente(db, video):
    _event(db, video.id, "click", NOW - timedelta(hours=2))
    metrics_rollup.roll_hourly(db, now=NOW)
    metrics_rollup.roll_hourly(db, now=NOW)
    assert sum(r.clicks for r in _hourly(db, video.id).values()) == 1


def test_rollup_continua_de_onde_parou(db, video):
    _event(db, video.id, "click", NOW - timedelta(hours=2))
    metrics_rollup.roll_hourly(db, now=NOW)
    _event(db, video.id, "click", NOW + timedelta(minutes=5))
    metrics_rollup.roll_hourly(db, now=NOW + timedelta(hours=1))
    assert sum(r.clicks for r in _hourly(db, video.id).values()) == 2


def test_rollup_de_retencao_fecha_dias_encerrados(db, video):
    yesterday = (NOW - timedelta(days=1)).date()
    _session(db, video.id, "a", yesterday, [[0, 3]])
    _session(db, video.id, "b", yesterday, [[1, 2]])
    _session(db, video.id, "c", NOW.date(), [[0, 1]])  # dia corrente fica de fora

    metrics_rollup.roll_daily(db, now=NOW)

    rows = db.query(RetentionDaily).filter_by(video_id=video.id).all()
    assert len(rows) == 1
    assert rows[0].day == yesterday
    assert rows[0].sessions == 2
    assert list(rows[0].counts) == [1, 2, 1]
    assert rows[0].watch_seconds == pytest.approx(4)


def test_rollup_diario_guarda_visitantes_unicos(db, video):
    day = NOW - timedelta(days=1)
    for session_id in ("a", "a", "b"):
        _event(db, video.id, "impression", day, session_id)
    _event(db, video.id, "play", day, "a")

    metrics_rollup.roll_daily(db, now=NOW)

    row = db.query(MetricsDaily).filter_by(video_id=video.id).one()
    assert (row.day, row.unique_impressions, row.unique_plays) == (day.date(), 2, 1)


def test_limpeza_so_apaga_bruto_ja_consolidado(db, video):
    old = NOW - timedelta(days=100)
    _event(db, video.id, "play", old, "velho")
    _session(db, video.id, "velho", old.date(), [[0, 5]])

    metrics_rollup.purge_raw(db, now=NOW, keep_days=90)  # sem rollup ainda: nada some
    assert db.query(func.count(VideoAnalytics.id)).filter_by(video_id=video.id).scalar() == 1

    metrics_rollup.run_all(db, now=NOW, keep_days=90)
    assert db.query(func.count(VideoAnalytics.id)).filter_by(video_id=video.id).scalar() == 0
    assert db.query(VideoWatchSession).filter_by(video_id=video.id).count() == 0
    # O consolidado continua lá
    assert sum(r.plays for r in _hourly(db, video.id).values()) == 1


def test_curva_reduzida_mantem_a_forma():
    curve = downsample_curve([10, 10, 8, 8, 6, 6], sessions=10, max_points=3)
    assert curve == {"bucket_seconds": 2, "sessions": 10, "values": [1.0, 0.8, 0.6]}


def test_curva_sem_sessoes_e_vazia():
    assert downsample_curve([], sessions=0) == {"bucket_seconds": 1, "sessions": 0, "values": []}


# --- endpoint /metrics lendo rollup + parte ao vivo ------------------------------------

def test_metrics_soma_consolidado_com_o_que_ainda_nao_foi_consolidado(db, video, logged):
    now = datetime.now(UTC)
    _event(db, video.id, "impression", now - timedelta(hours=5), "a")
    _event(db, video.id, "play", now - timedelta(hours=5), "a")
    metrics_rollup.roll_hourly(db, now=now)
    # Evento consolidado sai do bruto (simula a limpeza) e um novo chega depois do rollup
    db.query(VideoAnalytics).filter_by(video_id=video.id).delete()
    db.commit()
    _event(db, video.id, "impression", now, "b")
    _event(db, video.id, "progress_50", now, "b")

    body = client.get(f"/videos/{video.id}/metrics?period=all").json()

    assert body["total_impressions"] == 2
    assert body["total_plays"] == 1
    assert body["retention"]["50%"] == 1
    assert sum(h["impressions"] for h in body["hourly_distribution"]) == 2


def test_metrics_conta_total_e_unicos_somando_consolidado_e_ao_vivo(db, video, logged):
    now = datetime.now(UTC)
    ontem = now - timedelta(days=1)
    for session_id in ("a", "a", "b"):
        _event(db, video.id, "impression", ontem, session_id)
    metrics_rollup.run_all(db, now=now)
    for session_id in ("a", "c"):
        _event(db, video.id, "impression", now, session_id)

    body = client.get(f"/videos/{video.id}/metrics?period=all").json()

    assert body["total_impressions"] == 5
    # únicos por dia: ontem {a, b} + hoje {a, c}
    assert body["unique_impressions"] == 4


def test_metrics_entrega_curva_de_retencao_e_tempo_medio_real(db, video, logged):
    now = datetime.now(UTC)
    yesterday = (now - timedelta(days=1)).date()
    _session(db, video.id, "a", yesterday, [[0, 4]])
    metrics_rollup.roll_daily(db, now=now)
    _session(db, video.id, "b", now.date(), [[0, 2]])

    body = client.get(f"/videos/{video.id}/metrics?period=all").json()

    curve = body["retention_curve"]
    assert curve["sessions"] == 2
    assert curve["values"][:4] == [1.0, 1.0, 0.5, 0.5]
    assert body["avg_watch_time_seconds"] == pytest.approx(3)


def test_distribuicao_por_hora_usa_horario_de_brasilia(db, video, logged):
    at = datetime.now(UTC).replace(hour=15, minute=0, second=0, microsecond=0)
    if at > datetime.now(UTC):
        at -= timedelta(days=1)
    _event(db, video.id, "impression", at, "a")

    body = client.get(f"/videos/{video.id}/metrics?period=all").json()

    by_hour = {h["hour"]: h["impressions"] for h in body["hourly_distribution"]}
    assert by_hour[12] == 1


# --- regra do dono (v1.0.9): marcos por pessoa única que deu play; alcance da oferta --------

def test_marcos_contam_pessoas_unicas_que_deram_play(db, video, logged):
    now = datetime.now(UTC)
    ontem = now - timedelta(days=1)
    for at in (ontem, now):  # uma parte consolidada, outra ao vivo
        _event(db, video.id, "play", at, f"real-{at.date()}")
        _event(db, video.id, "progress_25", at, f"real-{at.date()}")
        _event(db, video.id, "progress_25", at, f"real-{at.date()}")  # recarregou: mesma pessoa
        _event(db, video.id, "progress_25", at, f"fantasma-{at.date()}")  # autoplay mudo, sem play
        if at == ontem:
            metrics_rollup.run_all(db, now=now)

    body = client.get(f"/videos/{video.id}/metrics?period=all").json()

    assert body["retention"]["25%"] == 2


def test_dia_sem_play_conta_todas_as_pessoas_do_marco(db, video, logged):
    now = datetime.now(UTC)
    ontem = now - timedelta(days=1)
    for sid in ("a", "a", "b"):
        _event(db, video.id, "progress_50", ontem, sid)
    metrics_rollup.run_all(db, now=now)

    body = client.get(f"/videos/{video.id}/metrics?period=all").json()

    assert body["retention"]["50%"] == 2


def test_alcance_da_oferta_vem_da_curva_por_segundo(db, video, logged):
    video.player_settings = {"cta_time": 2}
    db.commit()
    now = datetime.now(UTC)
    _session(db, video.id, "a", now.date(), [[0, 4]])
    _session(db, video.id, "b", now.date(), [[0, 1.5]])

    cta = client.get(f"/videos/{video.id}/metrics?period=all").json()["cta_metric"]

    assert cta == {"cta_time_seconds": 2, "cta_time_formatted": "00:02", "audience_reached": 1, "retention_percent": 50.0}


def test_sem_oferta_configurada_nao_ha_metrica(db, video, logged):
    assert client.get(f"/videos/{video.id}/metrics?period=all").json()["cta_metric"] is None
