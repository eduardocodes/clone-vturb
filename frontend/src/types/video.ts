export type SmartAutoplaySize = 'mini' | 'small' | 'medium' | 'large'

export interface SmartAutoplaySettings {
  enabled: boolean
  mode?: 'smart' | 'direct'
  text?: string
  subtext?: string
  button_color?: string
  button_text?: string
  restart_on_unmute?: boolean
  size?: SmartAutoplaySize
}

export interface FloatingPlayerSettings {
  enabled: boolean
  position?: 'bottom-right' | 'bottom-left'
  width?: number
  closeable?: boolean
}

export interface PitchDelaySettings {
  enabled: boolean
  time: number
  target_css_selector?: string
  auto_scroll?: boolean
  scroll_offset?: number
  persistence?: boolean
}

export interface PixelEventConfig {
  trigger: 'percent_25' | 'percent_50' | 'percent_75' | 'percent_100' | 'pitch'
  event_name: string
  enabled: boolean
}

export interface TrackingPixelsSettings {
  enabled: boolean
  facebook_pixel_id?: string
  google_analytics_id?: string
  tiktok_pixel_id?: string
  events?: PixelEventConfig[]
}

export interface DomainProtectionSettings {
  enabled: boolean
  allowed_domains?: string[]
  anti_download?: boolean
}

export interface PlayerControlsConfig {
  rewind_10s?: boolean
  forward_10s?: boolean
  volume?: boolean
  fullscreen?: boolean
  speed_control?: boolean
  progress_bar?: boolean
  video_time?: boolean
}

export interface ChapterItem {
  id: string
  time: string
  seconds: number
  title: string
}

export interface ChaptersSettings {
  enabled: boolean
  items: ChapterItem[]
}

export type SmartProgressIntensity = 'suave' | 'medio' | 'forte'

export interface SmartProgressSettings {
  enabled: boolean
  intensity: SmartProgressIntensity
}

export interface PlayerSettings {
  primary_color: string
  autoplay: boolean
  show_controls: boolean
  border_radius?: number
  aspect_ratio?: '16:9' | '9:16'
  cta_enabled: boolean
  cta_time: number
  cta_text: string
  cta_link: string
  play_button_shape?: 'circle' | 'rounded' | 'square' | 'minimal'
  play_button_size?: 'small' | 'medium' | 'large'
  default_width?: string
  default_ratio?: string
  turbo_enabled?: boolean
  playback_rate?: number
  smart_autoplay?: SmartAutoplaySettings
  floating_player?: FloatingPlayerSettings
  pitch_delay?: PitchDelaySettings
  tracking_pixels?: TrackingPixelsSettings
  domain_protection?: DomainProtectionSettings
  controls_config?: PlayerControlsConfig
  chapters?: ChaptersSettings
  smart_progress?: SmartProgressSettings
  transparent_background?: boolean
  remove_black_bars?: boolean
  fit_mode?: 'cover' | 'contain'
  /** Cookie da LP com o id externo (xid) repassado pelo script de embed. Padrão: `_eid` */
  external_id_cookie?: string
}


export interface Video {
  id: string
  title: string
  video_url: string
  thumbnail_url?: string
  duration: number
  plays_count?: number
  player_settings: PlayerSettings
  /** Processamento da mídia no servidor (HLS) */
  status?: 'ready' | 'processing' | 'failed'
  /** Master playlist do HLS gerado pelo worker; sem ela o player usa o MP4 de video_url */
  hls_url?: string | null
  processing_error?: string | null
  created_at: string
  updated_at: string
}

/** Curva por segundo: fração das sessões que assistiu cada faixa de `bucket_seconds`. */
export interface RetentionCurve {
  bucket_seconds: number
  sessions: number
  values: number[]
}

export interface HourlyMetric {
  hour: number
  label: string
  impressions: number
  plays: number
  clicks?: number
}

export interface PeakHour {
  hour: number
  label: string
  impressions: number
  plays: number
  total_activity: number
}

export interface CtaMetric {
  cta_time_seconds: number
  cta_time_formatted: string
  audience_reached: number
  retention_percent: number
}

export interface VideoMetrics {
  video_id: string
  period?: string
  start_date?: string | null
  end_date?: string | null
  total_impressions: number
  unique_impressions?: number
  total_plays: number
  unique_plays?: number
  play_rate: number
  total_clicks: number
  ctr: number
  avg_watch_time_seconds: number
  retention: {
    '25%': number
    '50%': number
    '75%': number
    '100%': number
  }
  retention_curve?: RetentionCurve | null
  hourly_distribution?: HourlyMetric[]
  peak_hour?: PeakHour | null
  cta_metric?: CtaMetric | null
}
