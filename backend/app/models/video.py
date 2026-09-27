import uuid
from datetime import datetime, timezone
from sqlalchemy import BigInteger, Column, Date, String, Float, Integer, DateTime, ForeignKey, Index, JSON, PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base

def get_utc_now():
    return datetime.now(timezone.utc)


# Play repetido em rajada (StrictMode, autoplay + clique) da mesma sessão é ignorado.
# Os demais marcos são protegidos no player (uma vez por carregamento); recarregar
# a página conta de novo (ver contracts/analytics-events.json).
BURST_DEDUP_EVENT_TYPES = ("play",)
BURST_DEDUP_SECONDS = 1

class Video(Base):
    __tablename__ = "videos"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    video_url = Column(String(1024), nullable=False)
    thumbnail_url = Column(String(1024), nullable=True)
    duration = Column(Float, default=0.0)
    player_settings = Column(JSON, default=lambda: {
        "primary_color": "#6366f1",
        "autoplay": False,
        "show_controls": True,
        "cta_enabled": False,
        "cta_time": 0,
        "cta_text": "Comprar Agora",
        "cta_link": "https://example.com",
        "controls_config": {
            "rewind_10s": True,
            "forward_10s": True,
            "volume": True,
            "fullscreen": True,
            "speed_control": True
        }
    })
    created_at = Column(DateTime(timezone=True), default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now)

    # --- Mídia no storage (contexto de Mídia; não expor no endpoint público) ---
    # Chave do arquivo original no storage (ex.: videos/<uuid>/source.mp4). Nula para URL externa.
    storage_key = Column(String(512), nullable=True)
    source_size_bytes = Column(BigInteger, nullable=True)
    # ready | processing | failed (processamento de HLS)
    status = Column(String(20), nullable=False, default="ready", server_default="ready")
    # Master playlist do HLS (videos/<uuid>/hls/<job_id>/master.m3u8). Nula até o worker terminar.
    hls_url = Column(String(1024), nullable=True)
    # Motivo curto da falha do processamento (o detalhe fica no log e em jobs.last_error)
    processing_error = Column(String(500), nullable=True)

    analytics = relationship("VideoAnalytics", back_populates="video", cascade="all, delete-orphan")


class VideoAnalytics(Base):
    __tablename__ = "video_analytics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True) # impression, play, progress_25, progress_50, progress_75, progress_100, click
    watch_time_seconds = Column(Float, default=0.0)
    session_id = Column(String(100), nullable=True)
    referer = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, index=True)

    video = relationship("Video", back_populates="analytics")

    __table_args__ = (
        Index("ix_video_analytics_video_type_created", "video_id", "event_type", "created_at"),
    )


class VideoWatchSession(Base):
    """Trechos do vídeo assistidos por uma sessão num dia (base da curva de retenção)."""
    __tablename__ = "video_watch_sessions"

    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(String(100), nullable=False)
    event_date = Column(Date, nullable=False)
    # Lista ordenada e sem sobreposição de [início, fim] em segundos do vídeo
    ranges = Column(JSON, nullable=False, default=list)
    watched_seconds = Column(Float, nullable=False, default=0.0)
    duration = Column(Float, nullable=False, default=0.0)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    __table_args__ = (
        PrimaryKeyConstraint("video_id", "session_id", "event_date"),
        Index("ix_video_watch_sessions_date", "event_date"),
    )
