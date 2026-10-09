import { getApiBaseUrl } from './apiConfig'
import type { ViewerAttributionParams } from '../components/embed/viewerAttribution'

export type ViewerAttributionPayload = ViewerAttributionParams & { session_id: string }

/** Fire-and-forget: falha aqui nunca pode atrapalhar o playback. */
export function sendViewerAttribution(videoId: string, payload: ViewerAttributionPayload): void {
  try {
    fetch(`${getApiBaseUrl()}/videos/${encodeURIComponent(videoId)}/attribution`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(() => undefined)
  } catch {
    // ignora: origem do espectador é best-effort
  }
}
