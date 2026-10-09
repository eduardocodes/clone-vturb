"""Origem do espectador: id externo opaco (xid) e UTMs da LP, first-touch por sessão.

O Smart VSL não interpreta esses valores; só guarda e exporta (/api/v1/export).
Também declara os índices que o export usa nas tabelas de telemetria, para não
mexer nos models upstream (o Index se liga à tabela pela coluna).
"""
from sqlalchemy import Column, DateTime, ForeignKey, Index, PrimaryKeyConstraint, String, func

from app.core.database import Base
from app.models.video import VideoAnalytics, VideoWatchSession

XID_MAX_LENGTH = 100
UTM_MAX_LENGTH = 512
UTM_FIELDS = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")


class ViewerAttribution(Base):
    __tablename__ = "viewer_attribution"

    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    session_id = Column(String(100), nullable=False)
    external_id = Column(String(XID_MAX_LENGTH), nullable=True)
    utm_source = Column(String(UTM_MAX_LENGTH), nullable=True)
    utm_medium = Column(String(UTM_MAX_LENGTH), nullable=True)
    utm_campaign = Column(String(UTM_MAX_LENGTH), nullable=True)
    utm_content = Column(String(UTM_MAX_LENGTH), nullable=True)
    utm_term = Column(String(UTM_MAX_LENGTH), nullable=True)
    first_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (PrimaryKeyConstraint("video_id", "session_id"),)


# Export: eventos de uma (vídeo, sessão, dia) e linhas do watch alteradas desde T
Index(
    "ix_video_analytics_video_session_created",
    VideoAnalytics.video_id,
    VideoAnalytics.session_id,
    VideoAnalytics.created_at,
)
Index("ix_video_watch_sessions_updated_at", VideoWatchSession.updated_at)
