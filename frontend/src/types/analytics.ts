/** Eventos que o player envia para POST /videos/{id}/events (contrato: contracts/analytics-events.json). */
export const EVENT_TYPES = [
  'impression',
  'play',
  'progress_25',
  'progress_50',
  'progress_75',
  'progress_100',
  'click',
  'cta_reached',
  'pitch_reached',
] as const

export type AnalyticsEventType = (typeof EVENT_TYPES)[number]

/** Trechos assistidos pela sessão, em segundos do vídeo: [[início, fim], ...] */
export type WatchRanges = [number, number][]

export interface WatchRangesPayload {
  session_id: string
  duration: number
  ranges: WatchRanges
}
