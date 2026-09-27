"""Modelo de leitura das métricas (consolidado pelo worker a partir dos eventos brutos).

O painel lê o consolidado até a watermark de cada rollup e soma o bruto depois dela,
então os números ficam em dia mesmo se o worker atrasar.
"""
from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, PrimaryKeyConstraint, String
from sqlalchemy.dialects.postgresql import ARRAY

from app.core.database import Base


class MetricsHourly(Base):
    __tablename__ = "video_metrics_hourly"

    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    hour_utc = Column(DateTime(timezone=True), nullable=False)
    impressions = Column(Integer, nullable=False, default=0)
    plays = Column(Integer, nullable=False, default=0)
    clicks = Column(Integer, nullable=False, default=0)
    p25 = Column(Integer, nullable=False, default=0)
    p50 = Column(Integer, nullable=False, default=0)
    p75 = Column(Integer, nullable=False, default=0)
    p100 = Column(Integer, nullable=False, default=0)

    __table_args__ = (PrimaryKeyConstraint("video_id", "hour_utc"),)


class MetricsDaily(Base):
    """Visitantes únicos (sessões distintas) por dia; somar dias conta quem volta em outro dia.

    unique_pNN: pessoas que chegaram ao marco, só entre as que deram play no dia (o autoplay
    mudo atrás da capa não conta). Dia sem nenhum play conta todas as pessoas do marco.
    """
    __tablename__ = "video_metrics_daily"

    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    day = Column(Date, nullable=False)
    unique_impressions = Column(Integer, nullable=False, default=0)
    unique_plays = Column(Integer, nullable=False, default=0)
    unique_p25 = Column(Integer, nullable=False, default=0)
    unique_p50 = Column(Integer, nullable=False, default=0)
    unique_p75 = Column(Integer, nullable=False, default=0)
    unique_p100 = Column(Integer, nullable=False, default=0)

    __table_args__ = (PrimaryKeyConstraint("video_id", "day"),)


class RetentionDaily(Base):
    __tablename__ = "video_retention_daily"

    video_id = Column(String(36), ForeignKey("videos.id", ondelete="CASCADE"), nullable=False)
    day = Column(Date, nullable=False)
    sessions = Column(Integer, nullable=False, default=0)
    watch_seconds = Column(Float, nullable=False, default=0.0)
    # counts[s] = sessões que assistiram o segundo s do vídeo
    counts = Column(ARRAY(Integer), nullable=False, default=list)

    __table_args__ = (PrimaryKeyConstraint("video_id", "day"),)


class RollupState(Base):
    """Até onde cada rollup já consolidou (exclusivo)."""
    __tablename__ = "metrics_rollup_state"

    name = Column(String(50), primary_key=True)
    rolled_until = Column(DateTime(timezone=True), nullable=False)
