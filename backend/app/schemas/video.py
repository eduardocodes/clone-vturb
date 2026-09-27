from typing import Optional, Dict, Any, List, Literal, get_args
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator

class SmartAutoplaySettings(BaseModel):
    model_config = ConfigDict(extra="allow")
    enabled: bool = False
    mode: Optional[str] = "smart"  # 'smart' (chamada para desmutar) ou 'direct' (autoplay direto com som)
    text: str = "Seu vídeo já começou!"
    subtext: str = "Clique no botão abaixo para ativar o som"
    button_color: str = "#ef4444"
    button_text: str = "CLIQUE PARA OUVIR"
    restart_on_unmute: bool = False
    size: Optional[str] = "medium"

class FloatingPlayerSettings(BaseModel):
    model_config = ConfigDict(extra="allow")
    enabled: bool = False
    position: str = "bottom-right"
    width: int = 320
    closeable: bool = True

class PitchDelaySettings(BaseModel):
    model_config = ConfigDict(extra="allow")
    enabled: bool = False
    time: int = 60
    target_css_selector: str = ".delay-pitch"
    auto_scroll: bool = True
    scroll_offset: int = 50
    persistence: bool = True

class PixelEventConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    trigger: str
    event_name: str
    enabled: bool = True

class TrackingPixelsSettings(BaseModel):
    model_config = ConfigDict(extra="allow")
    enabled: bool = False
    facebook_pixel_id: Optional[str] = None
    google_analytics_id: Optional[str] = None
    tiktok_pixel_id: Optional[str] = None
    events: Optional[List[PixelEventConfig]] = None

class DomainProtectionSettings(BaseModel):
    model_config = ConfigDict(extra="allow")
    enabled: bool = False
    allowed_domains: List[str] = Field(default_factory=list)
    anti_download: bool = True

class PlayerControlsConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    rewind_10s: bool = True
    forward_10s: bool = True
    volume: bool = True
    fullscreen: bool = True
    speed_control: bool = True
    progress_bar: bool = True
    video_time: bool = True

class ChapterItem(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    time: str = "00:00"
    seconds: float = 0.0
    title: str = ""

class ChaptersSettings(BaseModel):
    model_config = ConfigDict(extra="allow")
    enabled: bool = False
    items: List[ChapterItem] = Field(default_factory=list)

class SmartProgressSettings(BaseModel):
    model_config = ConfigDict(extra="allow")
    enabled: bool = False
    intensity: Literal["suave", "medio", "forte"] = "medio"  # curva da barra: anda rapido no inicio e desacelera no fim

class PlayerSettings(BaseModel):
    model_config = ConfigDict(extra="allow")
    primary_color: str = "#6366f1"
    autoplay: bool = False
    show_controls: bool = True
    border_radius: Optional[int] = 0
    aspect_ratio: Optional[str] = "16:9"
    cta_enabled: bool = False
    cta_time: int = 0
    cta_text: str = "Comprar Agora"
    cta_link: str = "https://example.com"
    turbo_enabled: Optional[bool] = False
    playback_rate: Optional[float] = 1.0
    smart_autoplay: Optional[SmartAutoplaySettings] = None
    floating_player: Optional[FloatingPlayerSettings] = None
    pitch_delay: Optional[PitchDelaySettings] = None
    tracking_pixels: Optional[TrackingPixelsSettings] = None
    domain_protection: Optional[DomainProtectionSettings] = None
    controls_config: Optional[PlayerControlsConfig] = None
    chapters: Optional[ChaptersSettings] = None
    smart_progress: Optional[SmartProgressSettings] = None
    transparent_background: Optional[bool] = False
    remove_black_bars: Optional[bool] = True
    fit_mode: Optional[str] = "cover"



# Chave gerada por /uploads/init para o arquivo original do vídeo
STORAGE_KEY_PATTERN = r"^videos/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/source\.(mp4|webm|mov|m4v)$"


class VideoCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    # Com storage_key, a URL é derivada da chave no servidor e este valor é ignorado
    video_url: str = Field(..., min_length=1, max_length=1024)
    thumbnail_url: Optional[str] = Field(None, max_length=1024)
    duration: Optional[float] = 0.0
    player_settings: Optional[PlayerSettings] = None
    storage_key: Optional[str] = Field(None, pattern=STORAGE_KEY_PATTERN)
    source_size_bytes: Optional[int] = Field(None, ge=0)

class VideoUpdate(BaseModel):
    title: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    duration: Optional[float] = None
    player_settings: Optional[PlayerSettings] = None
    storage_key: Optional[str] = Field(None, pattern=STORAGE_KEY_PATTERN)
    source_size_bytes: Optional[int] = Field(None, ge=0)

class VideoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    video_url: str
    thumbnail_url: Optional[str] = None
    duration: float
    plays_count: Optional[int] = 0
    player_settings: Dict[str, Any]
    status: str = "ready"
    hls_url: Optional[str] = None
    processing_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

# Contrato com o player: contracts/analytics-events.json (teste de contrato nos dois lados)
EventType = Literal["impression", "play", "progress_25", "progress_50", "progress_75", "progress_100", "click", "cta_reached", "pitch_reached"]
EVENT_TYPES: tuple[str, ...] = get_args(EventType)
MAX_WATCH_SECONDS = 86400.0
MAX_WATCH_RANGES = 500


class AnalyticsEventCreate(BaseModel):
    event_type: EventType
    watch_time_seconds: Optional[float] = Field(0.0, ge=0, le=MAX_WATCH_SECONDS)
    session_id: Optional[str] = Field(None, max_length=100)
    # Truncado (não recusado): document.referrer pode ser longo em LPs com UTMs
    referer: Optional[str] = None


class WatchRangesPayload(BaseModel):
    """Trechos assistidos enviados pelo player via sendBeacon (união acumulada da sessão)."""
    session_id: str = Field(..., min_length=1, max_length=100)
    duration: float = Field(..., ge=0, le=MAX_WATCH_SECONDS)
    ranges: List[List[float]] = Field(..., max_length=MAX_WATCH_RANGES)

    @field_validator("ranges")
    @classmethod
    def _pairs(cls, value: List[List[float]]) -> List[List[float]]:
        if any(len(item) != 2 for item in value):
            raise ValueError("Cada trecho deve ser [início, fim].")
        return value

class HourlyMetric(BaseModel):
    hour: int
    label: str
    impressions: int
    plays: int
    clicks: int = 0

class PeakHour(BaseModel):
    hour: int
    label: str
    impressions: int
    plays: int
    total_activity: int

class RetentionCurve(BaseModel):
    bucket_seconds: int
    sessions: int
    values: List[float]

class CtaMetric(BaseModel):
    cta_time_seconds: int
    cta_time_formatted: str
    audience_reached: int
    retention_percent: float

class VideoMetricsResponse(BaseModel):
    video_id: str
    period: Optional[str] = "all"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    timezone: str = "America/Sao_Paulo (Horário de Brasília / UTC-3)"
    total_impressions: int
    unique_impressions: int
    total_plays: int
    unique_plays: int
    play_rate: float
    total_clicks: int
    ctr: float
    avg_watch_time_seconds: float
    retention: Dict[str, int]
    hourly_distribution: List[HourlyMetric] = []
    peak_hour: Optional[PeakHour] = None
    # Curva por segundo: fração das sessões que assistiu cada trecho de `bucket_seconds`
    retention_curve: Optional["RetentionCurve"] = None
    cta_metric: Optional[CtaMetric] = None


class BulkDeleteRequest(BaseModel):
    video_ids: List[str] = Field(..., min_length=1)


class BulkDeleteResponse(BaseModel):
    deleted_count: int
    deleted_ids: List[str]


