"""Consolidação periódica das métricas (roda no worker).

- roll_hourly: eventos brutos -> video_metrics_hourly, só horas encerradas.
- roll_daily: por dia encerrado, visitantes únicos (video_metrics_daily, a partir do
  bruto) e curva de retenção (video_retention_daily, a partir das sessões de trechos).
- purge_raw: apaga bruto antigo, mas só o que já está abaixo das watermarks.

Cada rollup processa [watermark, limite) e avança a watermark; rodar de novo com o
mesmo "agora" não faz nada. O painel lê o consolidado até a watermark e o bruto depois.
"""
import logging
from datetime import date, datetime, time, timedelta, timezone
from itertools import groupby
from typing import Optional

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.metrics import MetricsDaily, RetentionDaily, RollupState
from app.models.video import VideoAnalytics, VideoWatchSession
from app.services.watch_ranges import retention_counts

logger = logging.getLogger("projetovturb.metrics")

HOURLY = "hourly"
DAILY = "daily"
# Margem para transações que ainda estão gravando eventos da hora que acabou de fechar
HOUR_CLOSE_MARGIN = timedelta(minutes=2)
DEFAULT_KEEP_DAYS = 90


def _trunc_hour(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


def _day_start(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone.utc)


def watermark(db: Session, name: str) -> Optional[datetime]:
    row = db.get(RollupState, name)
    return row.rolled_until if row else None


def _set_watermark(db: Session, name: str, value: datetime) -> None:
    db.execute(
        pg_insert(RollupState)
        .values(name=name, rolled_until=value)
        .on_conflict_do_update(index_elements=["name"], set_={"rolled_until": value})
    )


def roll_hourly(db: Session, now: datetime) -> None:
    until = _trunc_hour(now - HOUR_CLOSE_MARGIN)
    start = watermark(db, HOURLY)
    if start is None:
        first = db.query(func.min(VideoAnalytics.created_at)).scalar()
        start = _trunc_hour(first) if first else until
    if start >= until:
        return

    db.execute(
        text("""
            INSERT INTO video_metrics_hourly
                (video_id, hour_utc, impressions, plays, clicks, p25, p50, p75, p100)
            SELECT
                video_id,
                date_trunc('hour', created_at AT TIME ZONE 'UTC') AT TIME ZONE 'UTC',
                count(*) FILTER (WHERE event_type = 'impression'),
                count(*) FILTER (WHERE event_type = 'play'),
                count(*) FILTER (WHERE event_type = 'click'),
                count(*) FILTER (WHERE event_type = 'progress_25'),
                count(*) FILTER (WHERE event_type = 'progress_50'),
                count(*) FILTER (WHERE event_type = 'progress_75'),
                count(*) FILTER (WHERE event_type = 'progress_100')
            FROM video_analytics
            WHERE created_at >= :start AND created_at < :until
            GROUP BY 1, 2
            ON CONFLICT (video_id, hour_utc) DO UPDATE SET
                impressions = EXCLUDED.impressions, plays = EXCLUDED.plays, clicks = EXCLUDED.clicks,
                p25 = EXCLUDED.p25, p50 = EXCLUDED.p50, p75 = EXCLUDED.p75, p100 = EXCLUDED.p100
        """),
        {"start": start, "until": until},
    )
    _set_watermark(db, HOURLY, until)
    db.commit()
    logger.info("Rollup por hora consolidado até %s", until.isoformat())


def roll_daily(db: Session, now: datetime) -> None:
    until_day = now.astimezone(timezone.utc).date()
    wm = watermark(db, DAILY)
    if wm is not None:
        day = wm.date()
    else:
        firsts = [
            db.query(func.min(VideoWatchSession.event_date)).scalar(),
            (lambda c: c.astimezone(timezone.utc).date() if c else None)(db.query(func.min(VideoAnalytics.created_at)).scalar()),
        ]
        day = min([d for d in firsts if d], default=until_day)

    while day < until_day:
        _roll_uniques(db, day)
        _roll_retention(db, day)
        day += timedelta(days=1)
        _set_watermark(db, DAILY, _day_start(day))
        db.commit()
    logger.info("Rollup diário consolidado até %s", until_day.isoformat())


def _roll_uniques(db: Session, day: date) -> None:
    db.execute(
        text("""
            INSERT INTO video_metrics_daily (video_id, day, unique_impressions, unique_plays)
            SELECT
                video_id,
                :day,
                count(DISTINCT session_id) FILTER (WHERE event_type = 'impression'),
                count(DISTINCT session_id) FILTER (WHERE event_type = 'play')
            FROM video_analytics
            WHERE created_at >= :start AND created_at < :end AND session_id IS NOT NULL
            GROUP BY video_id
            ON CONFLICT (video_id, day) DO UPDATE SET
                unique_impressions = EXCLUDED.unique_impressions,
                unique_plays = EXCLUDED.unique_plays
        """),
        {"day": day, "start": _day_start(day), "end": _day_start(day + timedelta(days=1))},
    )


def _roll_retention(db: Session, day: date) -> None:
    rows = (
        db.query(VideoWatchSession.video_id, VideoWatchSession.ranges, VideoWatchSession.watched_seconds)
        .filter(VideoWatchSession.event_date == day)
        .order_by(VideoWatchSession.video_id)
        .yield_per(500)
    )
    for video_id, group in groupby(rows, key=lambda r: r[0]):
        sessions = list(group)
        values = {
            "video_id": video_id, "day": day, "sessions": len(sessions),
            "watch_seconds": float(sum(r[2] or 0 for r in sessions)),
            "counts": retention_counts(r[1] for r in sessions),
        }
        db.execute(
            pg_insert(RetentionDaily).values(**values).on_conflict_do_update(
                index_elements=["video_id", "day"],
                set_={k: values[k] for k in ("sessions", "watch_seconds", "counts")},
            )
        )


def purge_raw(db: Session, now: datetime, keep_days: int = DEFAULT_KEEP_DAYS) -> None:
    cutoff = now - timedelta(days=keep_days)
    hourly_wm = watermark(db, HOURLY)
    daily_wm = watermark(db, DAILY)
    if hourly_wm is not None and daily_wm is not None:
        # O bruto alimenta os dois rollups: só sai o que ambos já consolidaram
        limit = min(cutoff, hourly_wm, daily_wm)
        deleted = db.query(VideoAnalytics).filter(VideoAnalytics.created_at < limit).delete(synchronize_session=False)
        logger.info("Limpeza: %s eventos brutos anteriores a %s", deleted, limit.isoformat())
    if daily_wm is not None:
        limit_day = min(cutoff.date(), daily_wm.date())
        deleted = (
            db.query(VideoWatchSession)
            .filter(VideoWatchSession.event_date < limit_day)
            .delete(synchronize_session=False)
        )
        logger.info("Limpeza: %s sessões de trechos anteriores a %s", deleted, limit_day.isoformat())
    db.commit()


def run_all(db: Session, now: Optional[datetime] = None, keep_days: int = DEFAULT_KEEP_DAYS) -> None:
    now = now or datetime.now(timezone.utc)
    roll_hourly(db, now)
    roll_daily(db, now)
    purge_raw(db, now, keep_days)
