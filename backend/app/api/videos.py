import logging
import os
import shutil
import uuid
from typing import List, Optional
from pathlib import Path
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query

BRT_TZ = ZoneInfo("America/Sao_Paulo")

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.models.video import Video, VideoAnalytics
from app.models.user import User
from app.api.deps import get_current_user
from app.core.rate_limit import rate_limit
from app.services.storage import StorageNotConfigured, storage_service
from app.schemas.video import (
    VideoCreate,
    VideoUpdate,
    VideoResponse,
    AnalyticsEventCreate,
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
    rows = (
        db.query(VideoAnalytics.video_id, func.count(VideoAnalytics.id))
        .filter(VideoAnalytics.event_type == "play")
        .group_by(VideoAnalytics.video_id)
        .all()
    )
    return {row[0]: row[1] for row in rows}


def get_single_plays_count(db: Session, video_id: str) -> int:
    return (
        db.query(func.count(VideoAnalytics.id))
        .filter(VideoAnalytics.video_id == video_id, VideoAnalytics.event_type == "play")
        .scalar()
        or 0
    )


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
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vídeo não encontrado.")

    # Prevenção de duplicação por disparo simultâneo ou StrictMode da mesma sessão (debounce de 1s para play)
    if event.session_id and event.event_type == "play":
        recent_cutoff = datetime.now(timezone.utc) - timedelta(seconds=1)
        existing = (
            db.query(VideoAnalytics)
            .filter(
                VideoAnalytics.video_id == video_id,
                VideoAnalytics.session_id == event.session_id,
                VideoAnalytics.event_type == "play",
                VideoAnalytics.created_at >= recent_cutoff,
            )
            .first()
        )
        if existing:
            return {"status": "ignored_duplicate", "event": event.event_type}

    record = VideoAnalytics(
        video_id=video_id,
        event_type=event.event_type,
        watch_time_seconds=event.watch_time_seconds or 0.0,
        session_id=event.session_id,
        referer=event.referer
    )
    db.add(record)
    db.commit()
    return {"status": "ok", "event": event.event_type}


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

    base_query = db.query(VideoAnalytics).filter(VideoAnalytics.video_id == video_id)
    if start_dt:
        base_query = base_query.filter(VideoAnalytics.created_at >= start_dt)
    if end_dt:
        base_query = base_query.filter(VideoAnalytics.created_at <= end_dt)

    impressions = base_query.filter(VideoAnalytics.event_type == "impression").count()
    unique_impressions = (
        base_query.filter(
            VideoAnalytics.event_type == "impression",
            VideoAnalytics.session_id.isnot(None),
        )
        .with_entities(func.count(func.distinct(VideoAnalytics.session_id)))
        .scalar()
        or 0
    )

    plays = base_query.filter(VideoAnalytics.event_type == "play").count()
    unique_plays = (
        base_query.filter(
            VideoAnalytics.event_type == "play",
            VideoAnalytics.session_id.isnot(None),
        )
        .with_entities(func.count(func.distinct(VideoAnalytics.session_id)))
        .scalar()
        or 0
    )

    clicks = base_query.filter(VideoAnalytics.event_type == "click").count()

    prog_25 = base_query.filter(VideoAnalytics.event_type == "progress_25").count()
    prog_50 = base_query.filter(VideoAnalytics.event_type == "progress_50").count()
    prog_75 = base_query.filter(VideoAnalytics.event_type == "progress_75").count()
    prog_100 = base_query.filter(VideoAnalytics.event_type == "progress_100").count()

    avg_watch_time = (
        base_query.filter(VideoAnalytics.watch_time_seconds > 0)
        .with_entities(func.avg(VideoAnalytics.watch_time_seconds))
        .scalar()
        or 0.0
    )

    play_rate = round((plays / impressions * 100), 2) if impressions > 0 else 0.0
    ctr = round((clicks / plays * 100), 2) if plays > 0 else 0.0

    # Distribuição Horária no Fuso Horário Oficial de Brasília (00h às 23h BRT)
    hourly_data = {h: {"impressions": 0, "plays": 0, "clicks": 0} for h in range(24)}
    events_created_list = base_query.with_entities(
        VideoAnalytics.created_at, VideoAnalytics.event_type
    ).all()

    for ev_dt, ev_type in events_created_list:
        if ev_dt:
            # Garante que o timestamp UTC do banco seja convertido com precisão para o fuso de Brasília (BRT)
            if ev_dt.tzinfo is None:
                ev_dt = ev_dt.replace(tzinfo=timezone.utc)
            ev_brt = ev_dt.astimezone(BRT_TZ)
            h = ev_brt.hour
            if ev_type == "impression":
                hourly_data[h]["impressions"] += 1
            elif ev_type == "play":
                hourly_data[h]["plays"] += 1
            elif ev_type == "click":
                hourly_data[h]["clicks"] += 1

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
            "25%": prog_25,
            "50%": prog_50,
            "75%": prog_75,
            "100%": prog_100,
        },
        hourly_distribution=hourly_distribution,
        peak_hour=peak_hour,
    )
