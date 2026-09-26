"""Leitura das métricas do painel: consolidado até a watermark + bruto depois dela."""
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone, tzinfo
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.metrics import MetricsDaily, MetricsHourly, RetentionDaily
from app.models.video import VideoAnalytics, VideoWatchSession
from app.services.metrics_rollup import DAILY, HOURLY, watermark
from app.services.watch_ranges import retention_counts, sum_counts

# Coluna do consolidado <-> tipo de evento bruto
EVENT_COLUMNS = {
    "impression": "impressions",
    "play": "plays",
    "click": "clicks",
    "progress_25": "p25",
    "progress_50": "p50",
    "progress_75": "p75",
    "progress_100": "p100",
}
MAX_CURVE_POINTS = 400


@dataclass
class EventTotals:
    totals: dict = field(default_factory=lambda: {e: 0 for e in EVENT_COLUMNS})
    # hora local (0-23) -> {evento: contagem}
    by_hour: dict = field(default_factory=lambda: {h: {e: 0 for e in EVENT_COLUMNS} for h in range(24)})

    def add(self, hour_utc: datetime, event_type: str, count: int, tz: tzinfo) -> None:
        if not count:
            return
        self.totals[event_type] += count
        if hour_utc.tzinfo is None:
            hour_utc = hour_utc.replace(tzinfo=timezone.utc)
        self.by_hour[hour_utc.astimezone(tz).hour][event_type] += count


def event_totals(db: Session, video_id: str, start: Optional[datetime], end: Optional[datetime], tz: tzinfo) -> EventTotals:
    result = EventTotals()
    wm = watermark(db, HOURLY)

    if wm is not None:
        q = db.query(MetricsHourly).filter(MetricsHourly.video_id == video_id, MetricsHourly.hour_utc < wm)
        if start:
            q = q.filter(MetricsHourly.hour_utc >= start.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0))
        if end:
            q = q.filter(MetricsHourly.hour_utc <= end)
        for row in q.all():
            for event_type, column in EVENT_COLUMNS.items():
                result.add(row.hour_utc, event_type, getattr(row, column), tz)

    hour = func.date_trunc("hour", VideoAnalytics.created_at)
    q = (
        db.query(hour, VideoAnalytics.event_type, func.count(VideoAnalytics.id))
        .filter(VideoAnalytics.video_id == video_id)
        .group_by(hour, VideoAnalytics.event_type)
    )
    raw_start = max(filter(None, [start, wm]), default=None)
    if raw_start:
        q = q.filter(VideoAnalytics.created_at >= raw_start)
    if end:
        q = q.filter(VideoAnalytics.created_at <= end)
    for hour_utc, event_type, count in q.all():
        if event_type in EVENT_COLUMNS:
            result.add(hour_utc, event_type, count, tz)
    return result


@dataclass
class RetentionTotals:
    sessions: int = 0
    watch_seconds: float = 0.0
    counts: list = field(default_factory=list)


def retention_totals(db: Session, video_id: str, start: Optional[datetime], end: Optional[datetime]) -> RetentionTotals:
    start_day = start.astimezone(timezone.utc).date() if start else None
    end_day = end.astimezone(timezone.utc).date() if end else None
    wm = watermark(db, DAILY)
    wm_day = wm.date() if wm else None
    result = RetentionTotals()
    curves = []

    if wm_day is not None:
        q = db.query(RetentionDaily).filter(RetentionDaily.video_id == video_id, RetentionDaily.day < wm_day)
        if start_day:
            q = q.filter(RetentionDaily.day >= start_day)
        if end_day:
            q = q.filter(RetentionDaily.day <= end_day)
        for row in q.all():
            result.sessions += row.sessions
            result.watch_seconds += row.watch_seconds
            curves.append(row.counts or [])

    q = db.query(VideoWatchSession.ranges, VideoWatchSession.watched_seconds).filter(VideoWatchSession.video_id == video_id)
    live_start = max(filter(None, [start_day, wm_day]), default=None)
    if live_start:
        q = q.filter(VideoWatchSession.event_date >= live_start)
    if end_day:
        q = q.filter(VideoWatchSession.event_date <= end_day)
    live = q.all()
    result.sessions += len(live)
    result.watch_seconds += float(sum(r[1] or 0 for r in live))
    curves.append(retention_counts(r[0] for r in live))

    result.counts = sum_counts(curves)
    return result


def unique_totals(db: Session, video_id: str, start: Optional[datetime], end: Optional[datetime]) -> tuple[int, int]:
    """(impressões únicas, plays únicos): sessões distintas por dia, somadas no período."""
    start_day = start.astimezone(timezone.utc).date() if start else None
    end_day = end.astimezone(timezone.utc).date() if end else None
    wm = watermark(db, DAILY)
    impressions = plays = 0

    if wm is not None:
        q = db.query(func.sum(MetricsDaily.unique_impressions), func.sum(MetricsDaily.unique_plays)).filter(
            MetricsDaily.video_id == video_id, MetricsDaily.day < wm.date()
        )
        if start_day:
            q = q.filter(MetricsDaily.day >= start_day)
        if end_day:
            q = q.filter(MetricsDaily.day <= end_day)
        rolled_impressions, rolled_plays = q.one()
        impressions += int(rolled_impressions or 0)
        plays += int(rolled_plays or 0)

    day = func.date(func.timezone("UTC", VideoAnalytics.created_at))
    q = (
        db.query(
            day,
            func.count(func.distinct(VideoAnalytics.session_id)).filter(VideoAnalytics.event_type == "impression"),
            func.count(func.distinct(VideoAnalytics.session_id)).filter(VideoAnalytics.event_type == "play"),
        )
        .filter(VideoAnalytics.video_id == video_id, VideoAnalytics.session_id.isnot(None))
        .group_by(day)
    )
    live_start = max(filter(None, [start, wm]), default=None)
    if live_start:
        q = q.filter(VideoAnalytics.created_at >= live_start)
    if end:
        q = q.filter(VideoAnalytics.created_at <= end)
    for _, day_impressions, day_plays in q.all():
        impressions += day_impressions
        plays += day_plays
    return impressions, plays


def downsample_curve(counts: list, sessions: int, max_points: int = MAX_CURVE_POINTS) -> dict:
    """Reduz a curva por segundo a no máximo `max_points` pontos (média por faixa), em fração."""
    if not counts or sessions <= 0:
        return {"bucket_seconds": 1, "sessions": sessions, "values": []}
    bucket = max(1, math.ceil(len(counts) / max_points))
    values = []
    for i in range(0, len(counts), bucket):
        chunk = counts[i:i + bucket]
        values.append(round(min(1.0, (sum(chunk) / len(chunk)) / sessions), 4))
    return {"bucket_seconds": bucket, "sessions": sessions, "values": values}


def plays_by_video(db: Session, video_ids: Optional[list] = None) -> dict:
    """Plays por vídeo (consolidado + bruto recente), para a listagem."""
    wm = watermark(db, HOURLY)
    result: dict = {}
    if wm is not None:
        q = db.query(MetricsHourly.video_id, func.sum(MetricsHourly.plays)).filter(MetricsHourly.hour_utc < wm)
        if video_ids is not None:
            q = q.filter(MetricsHourly.video_id.in_(video_ids))
        for vid, total in q.group_by(MetricsHourly.video_id).all():
            result[vid] = int(total or 0)
    q = db.query(VideoAnalytics.video_id, func.count(VideoAnalytics.id)).filter(VideoAnalytics.event_type == "play")
    if wm is not None:
        q = q.filter(VideoAnalytics.created_at >= wm)
    if video_ids is not None:
        q = q.filter(VideoAnalytics.video_id.in_(video_ids))
    for vid, total in q.group_by(VideoAnalytics.video_id).all():
        result[vid] = result.get(vid, 0) + int(total)
    return result
