import { useRef, useEffect } from 'react'
import type { Video } from '../types/video'
import { sendTelemetryEvent, sendWatchRanges } from '../services/api'
import { WatchRangeTracker } from '../utils/watchRanges'
import { triggerTrackingPixels, initTrackingPixels } from '../utils/embedTracking'

/** Envio periódico dos trechos assistidos enquanto houver novidade. */
const WATCH_FLUSH_INTERVAL_MS = 30_000

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
  const watchTracker = useRef(new WatchRangeTracker())
  const durationRef = useRef(0)

  // Trechos assistidos (curva de retenção): a cada 30s e ao ocultar/fechar a página
  const flushWatchRanges = () => {
    const ranges = watchTracker.current.takeIfChanged()
    if (!ranges) return
    sendWatchRanges(videoId, { session_id: visitorId, duration: durationRef.current, ranges })
  }
  const flushRef = useRef(flushWatchRanges)
  useEffect(() => {
    flushRef.current = flushWatchRanges
  })

  useEffect(() => {
    const flush = () => flushRef.current()
    const onVisibility = () => {
      if (document.visibilityState === 'hidden') flush()
    }
    const interval = window.setInterval(flush, WATCH_FLUSH_INTERVAL_MS)
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('pagehide', flush)
    return () => {
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', onVisibility)
      window.removeEventListener('pagehide', flush)
      flush()
    }
  }, [])

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

  const handleTimeUpdateProgress = (current: number, total: number) => {
    if (!video) return
    if (total > 0) durationRef.current = total
    watchTracker.current.observe(current)

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

    // Gatilho de CTA Delay
    if (video.player_settings?.cta_enabled && current >= video.player_settings.cta_time) {
      setShowCta(true)
    }
  }

  const handleEndedTelemetry = (duration: number) => {
    if (duration > 0) durationRef.current = duration
    watchTracker.current.observe(duration)
    flushWatchRanges()
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
