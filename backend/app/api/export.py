"""Export máquina-a-máquina (M2M) para consumidores externos (ex.: TrackDash).

Auth: header X-Api-Key; sha256(chave) comparado em tempo constante com
EXPORT_API_KEY_SHA256. Env vazia = export desligado (404 em tudo); chave ausente
ou errada = 401. Contrato v1: contracts/export-v1.json.

viewer-sessions: uma linha por (video_id, session_id, dia UTC). As flags vêm dos
eventos do player daquele dia (nunca dos ranges); o tempo assistido vem de
video_watch_sessions, cujo event_date também é o dia UTC (ver _store_watch_ranges).
"""
import base64
import binascii
import hashlib
import hmac
import json
import logging
import time
from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.video import Video

logger = logging.getLogger("projetovturb.export")

EXPORT_VERSION = "1"
DEFAULT_LIMIT = 500
MAX_LIMIT = 1000


def require_export_key(x_api_key: Optional[str] = Header(None)) -> None:
    expected = (settings.EXPORT_API_KEY_SHA256 or "").strip().lower()
    if not expected:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    provided = hashlib.sha256((x_api_key or "").encode("utf-8")).hexdigest()
    if not x_api_key or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Chave de API inválida.")


router = APIRouter(
    prefix="/api/v1/export",
    tags=["Export"],
    dependencies=[Depends(require_export_key)],
)


@router.get("/ping")
def ping() -> dict:
    return {"ok": True, "version": EXPORT_VERSION}


def _positive_number(value: Any) -> Optional[float]:
    """Número > 0 como veio (int fica int); qualquer outra coisa vira null."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if value > 0 else None


def video_export_fields(video: Video) -> dict:
    ps = video.player_settings or {}
    pitch = ps.get("pitch_delay")
    pitch_time = _positive_number(pitch.get("time")) if isinstance(pitch, dict) and pitch.get("enabled") else None
    return {
        "id": video.id,
        "name": video.title,
        "duration_seconds": _positive_number(video.duration),
        "pitch_time_seconds": pitch_time,
        "cta_time_seconds": _positive_number(ps.get("cta_time")),
    }


@router.get("/videos")
def list_videos(db: Session = Depends(get_db)) -> dict:
    videos = db.query(Video).order_by(Video.created_at, Video.id).all()
    return {"videos": [video_export_fields(v) for v in videos]}


# --- viewer-sessions ---------------------------------------------------------------

def encode_cursor(row: dict) -> str:
    raw = json.dumps(
        {"u": _utc(row["updated_at"]).isoformat(), "v": row["video_id"], "s": row["session_id"], "d": row["day"].isoformat()},
        separators=(",", ":"),
    )
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, str, str, date]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        data = json.loads(raw)
        updated_at = datetime.fromisoformat(data["u"])
        video_id, session_id = data["v"], data["s"]
        day = date.fromisoformat(data["d"])
        if updated_at.tzinfo is None or not isinstance(video_id, str) or not isinstance(session_id, str):
            raise ValueError("cursor malformado")
    except (binascii.Error, ValueError, TypeError, KeyError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail="cursor inválido.") from exc
    return updated_at, video_id, session_id, day


# {op}/{cursor_clause} são fixos no código (nunca vêm da requisição).
# Candidatas: (vídeo, sessão, dia) com evento ou watch alterado desde o limite inferior.
# Com cursor, o limite sobe para o updated_at do cursor: linha depois dele tem
# updated_at >= cursor, então tem evento ou watch >= cursor. Mantém cada página barata.
VIEWER_SESSIONS_SQL = """
WITH keys AS (
    SELECT video_id, session_id, (created_at AT TIME ZONE 'UTC')::date AS day
    FROM video_analytics
    WHERE session_id IS NOT NULL AND created_at {op} :low
    UNION
    SELECT video_id, session_id, event_date AS day
    FROM video_watch_sessions
    WHERE updated_at {op} :low
),
agg AS (
    SELECT k.video_id, k.session_id, k.day,
        COALESCE(bool_or(a.event_type = 'impression'), false) AS loaded,
        COALESCE(bool_or(a.event_type = 'play'), false) AS played,
        COALESCE(bool_or(a.event_type = 'progress_25'), false) AS p25,
        COALESCE(bool_or(a.event_type = 'progress_50'), false) AS p50,
        COALESCE(bool_or(a.event_type = 'progress_75'), false) AS p75,
        COALESCE(bool_or(a.event_type = 'progress_100'), false) AS p100,
        COALESCE(bool_or(a.event_type = 'pitch_reached'), false) AS pitch_reached,
        COALESCE(bool_or(a.event_type = 'cta_reached'), false) AS cta_reached,
        COALESCE(bool_or(a.event_type = 'click'), false) AS clicked,
        max(a.created_at) AS last_event_at
    FROM keys k
    LEFT JOIN video_analytics a
        ON a.video_id = k.video_id
        AND a.session_id = k.session_id
        AND a.created_at >= (k.day::timestamp AT TIME ZONE 'UTC')
        AND a.created_at < ((k.day + 1)::timestamp AT TIME ZONE 'UTC')
    GROUP BY k.video_id, k.session_id, k.day
),
export_rows AS (
    SELECT agg.*,
        w.ranges, w.watched_seconds, w.duration,
        GREATEST(agg.last_event_at, w.updated_at) AS updated_at,
        va.external_id, va.utm_source, va.utm_medium, va.utm_campaign, va.utm_content, va.utm_term
    FROM agg
    LEFT JOIN video_watch_sessions w
        ON w.video_id = agg.video_id AND w.session_id = agg.session_id AND w.event_date = agg.day
    LEFT JOIN viewer_attribution va
        ON va.video_id = agg.video_id AND va.session_id = agg.session_id
)
SELECT * FROM export_rows
{cursor_clause}
ORDER BY updated_at, video_id, session_id, day
LIMIT :fetch
"""

FLAG_FIELDS = ("loaded", "played", "p25", "p50", "p75", "p100", "pitch_reached", "cta_reached", "clicked")
UTM_FIELDS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _serialize(row: dict) -> dict:
    return {
        "video_id": row["video_id"],
        "session_id": row["session_id"],
        "day": row["day"].isoformat(),
        "external_id": row["external_id"],
        **{f: row[f] for f in UTM_FIELDS},
        **{f: bool(row[f]) for f in FLAG_FIELDS},
        "watched_seconds": float(row["watched_seconds"]) if row["watched_seconds"] is not None else 0,
        "duration": float(row["duration"]) if row["duration"] is not None else None,
        "ranges": row["ranges"] if row["ranges"] is not None else [],
        "updated_at": _utc(row["updated_at"]).isoformat(),
    }


@router.get("/viewer-sessions")
def viewer_sessions(
    updated_since: datetime = Query(..., description="ISO 8601; exclusivo. Sem fuso = UTC."),
    cursor: Optional[str] = Query(None, description="next_cursor da página anterior (opaco)"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    db: Session = Depends(get_db),
) -> dict:
    started = time.monotonic()
    since = _utc(updated_since)
    params: dict[str, Any] = {"fetch": limit + 1, "low": since}
    op, cursor_clause = ">", ""
    if cursor:
        cu, cv, cs, cd = decode_cursor(cursor)
        cu = _utc(cu)
        if cu > since:
            op, params["low"] = ">=", cu
        cursor_clause = "WHERE (updated_at, video_id, session_id, day) > (:cu, :cv, :cs, :cd)"
        params.update(cu=cu, cv=cv, cs=cs, cd=cd)

    sql = text(VIEWER_SESSIONS_SQL.format(op=op, cursor_clause=cursor_clause))
    fetched = [dict(r) for r in db.execute(sql, params).mappings().all()]
    page = fetched[:limit]
    next_cursor = encode_cursor(page[-1]) if len(fetched) > limit else None

    logger.info(
        "export viewer-sessions: %d linhas, mais=%s, %.0f ms",
        len(page), next_cursor is not None, (time.monotonic() - started) * 1000,
    )
    return {"rows": [_serialize(r) for r in page], "next_cursor": next_cursor}
