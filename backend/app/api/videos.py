import logging
import os
import shutil
import uuid
from typing import List, Optional
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, UploadFile, File, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import insert as pg_insert

BRT_TZ = ZoneInfo("America/Sao_Paulo")

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import SessionLocal, get_db
from app.models.video import BURST_DEDUP_EVENT_TYPES, BURST_DEDUP_SECONDS, Video, VideoAnalytics, VideoWatchSession
from app.models.user import User
from app.api.deps import get_current_user
from app.core.rate_limit import rate_limit
from app.services.storage import StorageNotConfigured, storage_service
from app.services.watch_ranges import merge_ranges, watched_seconds
from app.services.metrics_query import downsample_curve, event_totals, plays_by_video, retention_totals, unique_totals
from app.schemas.video import (
    VideoCreate,
    VideoUpdate,
    VideoResponse,
    AnalyticsEventCreate,
    WatchRangesPayload,
    VideoMetricsResponse,
    HourlyMetric,
    PeakHour,
    BulkDeleteRequest,
    BulkDeleteResponse,
)

router = APIRouter(prefix="/videos", tags=["Videos"])
logger = logging.getLogger("projetovturb.videos")


def _video_folder(storage_key: str) -> str:
    """videos/<uuid>/source.mp4 -> videos/<uuid>/ (pasta com o original e, depois, o HLS)."""
    return storage_key.rsplit("/", 1)[0] + "/"


def cleanup_storage(storage_key: Optional[str] = None, thumbnail_url: Optional[str] = None) -> None:
    """Apaga do storage os arquivos de um vídeo. Melhor esforço: falha só vira log."""
    if storage_key:
        try:
            storage_service.delete_prefix(_video_folder(storage_key))
        except Exception as exc:
            logger.error(f"Falha ao apagar {storage_key} do storage: {exc}")
    thumb_key = storage_service.key_from_public_url(thumbnail_url) if thumbnail_url else None
    if thumb_key and thumb_key.startswith("thumbs/"):
        try:
            storage_service.delete_object(thumb_key)
        except Exception as exc:
            logger.error(f"Falha ao apagar a capa {thumb_key} do storage: {exc}")


def get_plays_count_map(db: Session) -> dict:
    return plays_by_video(db)


def get_single_plays_count(db: Session, video_id: str) -> int:
    return plays_by_video(db, [video_id]).get(video_id, 0)


@router.get("/", response_model=List[VideoResponse])
def list_videos(
    skip: Optional[int] = Query(0, ge=0),
    limit: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Video).order_by(Video.created_at.desc())
    if skip:
        query = query.offset(skip)
    if limit:
        query = query.limit(limit)
    videos = query.all()
    plays_map = get_plays_count_map(db)
    return [
        VideoResponse(
            id=v.id,
            title=v.title,
            video_url=v.video_url,
            thumbnail_url=v.thumbnail_url,
            duration=v.duration or 0.0,
            plays_count=plays_map.get(v.id, 0),
            player_settings=v.player_settings or {},
            status=v.status or "ready",
            created_at=v.created_at,
            updated_at=v.updated_at,
        )
        for v in videos
    ]


@router.post("/", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
def create_video(
    payload: VideoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = Video(
        title=payload.title,
        video_url=storage_service.public_url(payload.storage_key) if payload.storage_key else payload.video_url,
        storage_key=payload.storage_key,
        source_size_bytes=payload.source_size_bytes if payload.storage_key else None,
        thumbnail_url=payload.thumbnail_url,
        duration=payload.duration or 0.0,
        player_settings=payload.player_settings.model_dump() if payload.player_settings else {
            "primary_color": "#6366f1",
            "autoplay": False,
            "show_controls": True,
            "cta_enabled": False,
            "cta_time": 0,
            "cta_text": "Comprar Agora",
            "cta_link": "https://example.com"
        }
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    video.plays_count = 0
    return video


# Extensão aceita -> prefixo de MIME esperado. SVG fica fora: pode carregar script (XSS).
UPLOAD_EXTENSIONS = {
    ".mp4": "video/", ".webm": "video/", ".mov": "video/", ".m4v": "video/",
    ".png": "image/", ".jpg": "image/", ".jpeg": "image/", ".webp": "image/", ".gif": "image/",
}


@router.post("/upload")
def upload_video_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    ext = Path(file.filename or "").suffix.lower()
    expected_mime_prefix = UPLOAD_EXTENSIONS.get(ext)
    if expected_mime_prefix is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de arquivo não suportado: {ext}. Utilize MP4, WebM, MOV, PNG ou JPG."
        )
    if not (file.content_type or "").lower().startswith(expected_mime_prefix):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tipo do arquivo não corresponde à extensão."
        )

    try:
        file_url = storage_service.upload_file(
            file_obj=file.file,
            original_filename=file.filename,
            content_type=file.content_type
        )
    except StorageNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upload indisponível: storage não configurado."
        )

    return {
        "filename": file.filename,
        "url": file_url
    }


@router.post("/bulk-delete", response_model=BulkDeleteResponse)
def bulk_delete_videos(
    payload: BulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not payload.video_ids:
        return BulkDeleteResponse(deleted_count=0, deleted_ids=[])

    videos = db.query(Video).filter(Video.id.in_(payload.video_ids)).all()
    deleted_ids = [v.id for v in videos]
    media = [(v.storage_key, v.thumbnail_url) for v in videos]

    for video in videos:
        db.delete(video)
    db.commit()

    for storage_key, thumbnail_url in media:
        cleanup_storage(storage_key, thumbnail_url)

    return BulkDeleteResponse(
        deleted_count=len(deleted_ids),
        deleted_ids=deleted_ids
    )


@router.get("/{video_id}", response_model=VideoResponse)
def get_video(video_id: str, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vídeo não encontrado.")
    video.plays_count = get_single_plays_count(db, video.id)
    return video


@router.put("/{video_id}", response_model=VideoResponse)
def update_video(
    video_id: str,
    payload: VideoUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vídeo não encontrado.")

    stale_key: Optional[str] = None
    stale_thumbnail: Optional[str] = None

    if payload.title is not None:
        video.title = payload.title
    if payload.storage_key is not None:
        if video.storage_key and video.storage_key != payload.storage_key:
            stale_key = video.storage_key
        video.storage_key = payload.storage_key
        video.source_size_bytes = payload.source_size_bytes
        video.video_url = storage_service.public_url(payload.storage_key)
    elif payload.video_url is not None and payload.video_url != video.video_url:
        # Trocou por uma URL externa: o arquivo antigo do storage fica órfão
        stale_key = video.storage_key
        video.storage_key = None
        video.source_size_bytes = None
        video.video_url = payload.video_url
    if payload.thumbnail_url is not None and payload.thumbnail_url != video.thumbnail_url:
        stale_thumbnail = video.thumbnail_url
        video.thumbnail_url = payload.thumbnail_url
    if payload.player_settings is not None:
        video.player_settings = payload.player_settings.model_dump()

    db.commit()
    db.refresh(video)
    if stale_key or stale_thumbnail:
        cleanup_storage(stale_key, stale_thumbnail)
    video.plays_count = get_single_plays_count(db, video.id)
    return video


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(
    video_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vídeo não encontrado.")

    storage_key, thumbnail_url = video.storage_key, video.thumbnail_url
    db.delete(video)
    db.commit()
    cleanup_storage(storage_key, thumbnail_url)
    return None


@router.post(
    "/{video_id}/events",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("events", 120))],
)
def track_event(video_id: str, event: AnalyticsEventCreate, db: Session = Depends(get_db)):
    if not db.query(Video.id).filter(Video.id == video_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vídeo não encontrado.")

    # Disparo repetido em rajada (StrictMode, autoplay + clique) da mesma sessão é
    # ignorado. Recarregar a página depois conta de novo: total != únicos.
    if event.session_id and event.event_type in BURST_DEDUP_EVENT_TYPES:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=BURST_DEDUP_SECONDS)
        duplicate = (
            db.query(VideoAnalytics.id)
            .filter(
                VideoAnalytics.video_id == video_id,
                VideoAnalytics.event_type == event.event_type,
                VideoAnalytics.created_at >= cutoff,
                VideoAnalytics.session_id == event.session_id,
            )
            .first()
        )
        if duplicate:
            return {"status": "ignored_duplicate", "event": event.event_type}

    db.add(VideoAnalytics(
        video_id=video_id,
        event_type=event.event_type,
        watch_time_seconds=event.watch_time_seconds or 0.0,
        session_id=event.session_id,
        referer=event.referer[:512] if event.referer else None,
    ))
    db.commit()
    return {"status": "ok", "event": event.event_type}


MAX_WATCH_BODY_BYTES = 64 * 1024


@router.post(
    "/{video_id}/watch",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("watch", 60))],
)
async def track_watch_ranges(video_id: str, request: Request):
    """Trechos assistidos da sessão (base da curva de retenção).

    Aceita o corpo como texto: o player envia por navigator.sendBeacon com
    text/plain, que não dispara preflight de CORS e sobrevive ao fechar a aba.
    """
    raw = await request.body()
    if len(raw) > MAX_WATCH_BODY_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Payload grande demais.")
    try:
        payload = WatchRangesPayload.model_validate_json(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=jsonable_encoder(exc.errors(include_url=False, include_context=False)))

    found = await run_in_threadpool(_store_watch_ranges, video_id, payload)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vídeo não encontrado.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _store_watch_ranges(video_id: str, payload: WatchRangesPayload) -> bool:
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            return False
        # Vídeo sem duração cadastrada (URL externa, upload antes do processamento):
        # usa a duração que o navegador leu do arquivo
        if not video.duration and payload.duration > 0:
            video.duration = payload.duration
        today = datetime.now(timezone.utc).date()
        key = {"video_id": video_id, "session_id": payload.session_id, "event_date": today}
        db.execute(
            pg_insert(VideoWatchSession)
            .values(**key, ranges=[], watched_seconds=0.0, duration=payload.duration, updated_at=datetime.now(timezone.utc))
            .on_conflict_do_nothing(index_elements=["video_id", "session_id", "event_date"])
        )
        # Trava a linha: dois beacons da mesma sessão não perdem trechos um do outro
        row = db.query(VideoWatchSession).filter_by(**key).with_for_update().one()
        duration = max(row.duration or 0.0, payload.duration)
        merged = merge_ranges(row.ranges or [], payload.ranges, duration)
        row.ranges = merged
        row.watched_seconds = watched_seconds(merged)
        row.duration = duration
        row.updated_at = datetime.now(timezone.utc)
        db.commit()
        return True
    finally:
        db.close()


@router.get("/{video_id}/metrics", response_model=VideoMetricsResponse)
def get_video_metrics(
    video_id: str,
    period: Optional[str] = Query("all", description="today, yesterday, 7d, 30d, 1y, all, custom"),
    start_date: Optional[str] = Query(None, description="YYYY-MM-DD ou ISO"),
    end_date: Optional[str] = Query(None, description="YYYY-MM-DD ou ISO"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vídeo não encontrado.")

    now_brt = datetime.now(BRT_TZ)
    start_dt: Optional[datetime] = None
    end_dt: Optional[datetime] = None

    if period == "today":
        start_brt = now_brt.replace(hour=0, minute=0, second=0, microsecond=0)
        end_brt = now_brt
        start_dt = start_brt.astimezone(timezone.utc)
        end_dt = end_brt.astimezone(timezone.utc)
    elif period == "yesterday":
        yesterday_brt = now_brt - timedelta(days=1)
        start_brt = yesterday_brt.replace(hour=0, minute=0, second=0, microsecond=0)
        end_brt = yesterday_brt.replace(hour=23, minute=59, second=59, microsecond=999999)
        start_dt = start_brt.astimezone(timezone.utc)
        end_dt = end_brt.astimezone(timezone.utc)
    elif period in ("7d", "1week"):
        start_brt = now_brt - timedelta(days=7)
        end_brt = now_brt
        start_dt = start_brt.astimezone(timezone.utc)
        end_dt = end_brt.astimezone(timezone.utc)
    elif period in ("30d", "1month"):
        start_brt = now_brt - timedelta(days=30)
        end_brt = now_brt
        start_dt = start_brt.astimezone(timezone.utc)
        end_dt = end_brt.astimezone(timezone.utc)
    elif period in ("1y", "1year"):
        start_brt = now_brt - timedelta(days=365)
        end_brt = now_brt
        start_dt = start_brt.astimezone(timezone.utc)
        end_dt = end_brt.astimezone(timezone.utc)
    elif start_date or end_date:
        period = "custom"
        if start_date:
            try:
                if "T" in start_date:
                    parsed_s = datetime.fromisoformat(start_date)
                    start_brt = parsed_s if parsed_s.tzinfo else parsed_s.replace(tzinfo=BRT_TZ)
                else:
                    start_brt = datetime.fromisoformat(f"{start_date}T00:00:00").replace(tzinfo=BRT_TZ)
                start_dt = start_brt.astimezone(timezone.utc)
            except Exception:
                start_dt = None
        if end_date:
            try:
                if "T" in end_date:
                    parsed_e = datetime.fromisoformat(end_date)
                    end_brt = parsed_e if parsed_e.tzinfo else parsed_e.replace(tzinfo=BRT_TZ)
                else:
                    end_brt = datetime.fromisoformat(f"{end_date}T23:59:59.999999").replace(tzinfo=BRT_TZ)
                end_dt = end_brt.astimezone(timezone.utc)
            except Exception:
                end_dt = None
    else:
        period = "all"

    # Consolidado (rollup) até a watermark + eventos brutos depois dela: sempre em dia.
    # Únicos = sessões distintas por dia, somadas no período.
    events = event_totals(db, video_id, start_dt, end_dt, BRT_TZ)
    totals = events.totals
    impressions = totals["impression"]
    plays = totals["play"]
    unique_impressions, unique_plays = unique_totals(db, video_id, start_dt, end_dt)
    clicks = totals["click"]
    watch = retention_totals(db, video_id, start_dt, end_dt)
    avg_watch_time = (watch.watch_seconds / watch.sessions) if watch.sessions else 0.0

    play_rate = round((plays / impressions * 100), 2) if impressions > 0 else 0.0
    ctr = round((clicks / plays * 100), 2) if plays > 0 else 0.0

    hourly_data = {
        h: {"impressions": events.by_hour[h]["impression"], "plays": events.by_hour[h]["play"], "clicks": events.by_hour[h]["click"]}
        for h in range(24)
    }

    hourly_distribution: List[HourlyMetric] = []
    max_activity = -1
    peak_h: Optional[int] = None

    for h in range(24):
        impr = hourly_data[h]["impressions"]
        ply = hourly_data[h]["plays"]
        clk = hourly_data[h]["clicks"]
        activity = impr + ply
        if activity > max_activity and activity > 0:
            max_activity = activity
            peak_h = h
        hourly_distribution.append(
            HourlyMetric(
                hour=h,
                label=f"{h:02d}:00",
                impressions=impr,
                plays=ply,
                clicks=clk,
            )
        )

    peak_hour: Optional[PeakHour] = None
    if peak_h is not None:
        next_h = (peak_h + 1) % 24
        peak_hour = PeakHour(
            hour=peak_h,
            label=f"{peak_h:02d}:00 - {next_h:02d}:00",
            impressions=hourly_data[peak_h]["impressions"],
            plays=hourly_data[peak_h]["plays"],
            total_activity=max_activity,
        )

    start_date_iso = start_dt.astimezone(BRT_TZ).isoformat() if start_dt else None
    end_date_iso = end_dt.astimezone(BRT_TZ).isoformat() if end_dt else None

    return VideoMetricsResponse(
        video_id=video_id,
        period=period,
        start_date=start_date_iso,
        end_date=end_date_iso,
        timezone="America/Sao_Paulo (Horário de Brasília / UTC-3)",
        total_impressions=impressions,
        unique_impressions=unique_impressions,
        total_plays=plays,
        unique_plays=unique_plays,
        play_rate=play_rate,
        total_clicks=clicks,
        ctr=ctr,
        avg_watch_time_seconds=round(float(avg_watch_time), 2),
        retention={
            "25%": totals["progress_25"],
            "50%": totals["progress_50"],
            "75%": totals["progress_75"],
            "100%": totals["progress_100"],
        },
        hourly_distribution=hourly_distribution,
        peak_hour=peak_hour,
        retention_curve=downsample_curve(watch.counts, watch.sessions),
    )
