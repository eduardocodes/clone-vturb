import { useRef, useEffect } from 'react'
import type { Video } from '../types/video'
import { sendTelemetryEvent } from '../services/api'
import { triggerTrackingPixels, initTrackingPixels } from '../utils/embedTracking'

interface UseVideoTelemetryProps {
  video: Video | null
  videoId: string
  visitorId: string
  setShowCta: (show: boolean) => void
}

export function useVideoTelemetry({
  video,
  videoId,
  visitorId,
  setShowCta,
}: UseVideoTelemetryProps) {
  const progressSent = useRef<{ [key: string]: boolean }>({})
  const pixelEventsSent = useRef<{ [key: string]: boolean }>({})
  const pitchDelaySent = useRef(false)
  const impressionSent = useRef(false)
  const pixelsInitialized = useRef(false)

  useEffect(() => {
    if (video?.player_settings?.tracking_pixels?.enabled && !pixelsInitialized.current) {
      pixelsInitialized.current = true
      initTrackingPixels(video.player_settings.tracking_pixels)
    }
  }, [video])

  const dispatchPixelEvent = (triggerKey: 'percent_25' | 'percent_50' | 'percent_75' | 'percent_100' | 'pitch') => {
    if (pixelEventsSent.current[triggerKey]) return
    pixelEventsSent.current[triggerKey] = true
    triggerTrackingPixels(triggerKey, videoId, video?.player_settings?.tracking_pixels)
  }

  const trackImpression = () => {
    if (!impressionSent.current) {
      impressionSent.current = true
      sendTelemetryEvent(videoId, {
        event_type: 'impression',
        session_id: visitorId,
        referer: document.referrer || window.location.href,
      })
    }
  }

  const handleTimeUpdateProgress = (current: number, total: number, isSmartAutoplaying = false) => {
    // Enquanto estiver apenas rodando mudo atrás da capa do Smart Autoplay ("Clique para Ouvir"),
    // não contabiliza retenção nem alcance de oferta (CTA) antes de o lead clicar para assistir.
    if (!video || isSmartAutoplaying) return

    if (total > 0) {
      const pct = (current / total) * 100

      if (pct >= 25 && !progressSent.current['25']) {
        progressSent.current['25'] = true
        sendTelemetryEvent(videoId, { event_type: 'progress_25', watch_time_seconds: current, session_id: visitorId })
        dispatchPixelEvent('percent_25')
      }
      if (pct >= 50 && !progressSent.current['50']) {
        progressSent.current['50'] = true
        sendTelemetryEvent(videoId, { event_type: 'progress_50', watch_time_seconds: current, session_id: visitorId })
        dispatchPixelEvent('percent_50')
      }
      if (pct >= 75 && !progressSent.current['75']) {
        progressSent.current['75'] = true
        sendTelemetryEvent(videoId, { event_type: 'progress_75', watch_time_seconds: current, session_id: visitorId })
        dispatchPixelEvent('percent_75')
      }
    }

    // Gatilho de Pitch Delay (Conteúdo Oculto)
    if (video.player_settings?.pitch_delay?.enabled && !pitchDelaySent.current) {
      const pitchSeconds = video.player_settings.pitch_delay.time || 60
      if (current >= pitchSeconds) {
        pitchDelaySent.current = true
        sendTelemetryEvent(videoId, {
          event_type: 'pitch_reached',
          watch_time_seconds: current,
          session_id: visitorId,
        })
        dispatchPixelEvent('pitch')
        const payload = {
          type: 'VTURB_PITCH_REACHED',
          videoId,
          targetSelector: video.player_settings.pitch_delay.target_css_selector || '.delay-pitch',
          autoScroll: video.player_settings.pitch_delay.auto_scroll ?? true,
          scrollOffset: video.player_settings.pitch_delay.scroll_offset || 50,
          persistence: video.player_settings.pitch_delay.persistence ?? true,
        }
        if (typeof window !== 'undefined') {
          window.parent?.postMessage(payload, '*')
          window.postMessage(payload, '*')
          try {
            const el = document.querySelector(payload.targetSelector)
            if (el) (el as HTMLElement).style.display = 'block'
          } catch {}
        }
      }
    }

    // Gatilho de Momento da Oferta (CTA) - registra alcance único apenas de quem está assistindo
    const configuredCtaTime = Number(video.player_settings?.cta_time) || 0
    if (configuredCtaTime > 0 && current >= configuredCtaTime) {
      if (video.player_settings?.cta_enabled) {
        setShowCta(true)
      }
      if (!progressSent.current['cta_reached']) {
        progressSent.current['cta_reached'] = true
        sendTelemetryEvent(videoId, {
          event_type: 'cta_reached',
          watch_time_seconds: current,
          session_id: visitorId,
        })
      }
    }
  }

  const handleEndedTelemetry = (duration: number, isSmartAutoplaying = false) => {
    if (isSmartAutoplaying) return
    if (!progressSent.current['100']) {
      progressSent.current['100'] = true
      sendTelemetryEvent(videoId, {
        event_type: 'progress_100',
        watch_time_seconds: duration,
        session_id: visitorId,
      })
      dispatchPixelEvent('percent_100')
    }
  }

  return {
    trackImpression,
    handleTimeUpdateProgress,
    handleEndedTelemetry,
  }
}
