import type { ChapterItem, SmartProgressIntensity, SmartProgressSettings } from '../types/video'

/**
 * Progresso Inteligente: a barra anda rápido no início e desacelera no fim,
 * fazendo o vídeo parecer mais curto. Curva ease-out: visual(f) = 1 - (1 - f)^k.
 * Apenas visual — tempo real, telemetria e rótulo de tempo não mudam.
 */
export const SMART_PROGRESS_EXPONENTS: Record<SmartProgressIntensity, number> = {
  suave: 1.5,
  medio: 2,
  forte: 3,
}

export const DEFAULT_SMART_PROGRESS: SmartProgressSettings = { enabled: false, intensity: 'medio' }

const FALLBACK_DURATION = 60

export function resolveSmartProgress(settings?: Partial<SmartProgressSettings> | null): SmartProgressSettings {
  const intensity =
    settings?.intensity && settings.intensity in SMART_PROGRESS_EXPONENTS
      ? settings.intensity
      : DEFAULT_SMART_PROGRESS.intensity
  return { enabled: Boolean(settings?.enabled), intensity }
}

function safeDuration(duration: number): number {
  return Number.isFinite(duration) && duration > 0 ? duration : FALLBACK_DURATION
}

function linearFraction(currentTime: number, duration: number): number {
  if (!Number.isFinite(currentTime) || currentTime <= 0) return 0
  return Math.min(1, currentTime / safeDuration(duration))
}

function curve(fraction: number, cfg: SmartProgressSettings): number {
  if (!cfg.enabled) return fraction
  if (fraction >= 1) return 1
  return 1 - Math.pow(1 - fraction, SMART_PROGRESS_EXPONENTS[cfg.intensity])
}

/** Fração (0..1) que a barra deve exibir para o tempo atual. */
export function toVisualFraction(
  currentTime: number,
  duration: number,
  settings?: Partial<SmartProgressSettings> | null
): number {
  return curve(linearFraction(currentTime, duration), resolveSmartProgress(settings))
}

export interface ChapterSegment {
  /** Início real do capítulo em segundos */
  start: number
  /** Largura do segmento na barra (0..100) */
  widthPct: number
  /** Preenchimento do segmento (0..100) */
  fillPct: number
}

/** Segmentos de capítulos com limites e preenchimento passados pela curva. */
export function mapChapterSegments(
  items: ChapterItem[],
  duration: number,
  currentTime: number,
  settings?: Partial<SmartProgressSettings> | null
): ChapterSegment[] {
  const total = safeDuration(duration)
  const visualNow = toVisualFraction(currentTime, total, settings)

  return items.map((chap, idx, arr) => {
    const start = Math.max(0, chap.seconds)
    const end = idx < arr.length - 1 ? Math.max(start + 1, arr[idx + 1].seconds) : Math.max(start + 1, total)
    const visualStart = toVisualFraction(start, total, settings)
    const visualEnd = toVisualFraction(end, total, settings)
    const span = visualEnd - visualStart

    let fillPct = 0
    if (visualNow >= visualEnd) fillPct = 100
    else if (visualNow > visualStart && span > 0) fillPct = ((visualNow - visualStart) / span) * 100

    return { start, widthPct: span * 100, fillPct }
  })
}
