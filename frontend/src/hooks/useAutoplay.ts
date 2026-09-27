import { useEffect, useRef } from 'react'
import type { Video } from '../types/video'
import { sendTelemetryEvent } from '../services/api'

interface UseAutoplayProps {
  video: Video | null
  videoId: string
  visitorId: string
  videoRef: React.RefObject<HTMLVideoElement | null>
  setIsPlaying: (val: boolean) => void
  setIsMuted: (val: boolean) => void
  setIsSmartAutoplaying: (val: boolean) => void
  setShowDirectUnmuteBanner: (val: boolean) => void
  isPlayerVisible?: boolean
}

export function useAutoplay({
  video,
  videoId,
  visitorId,
  videoRef,
  setIsPlaying,
  setIsMuted,
  setIsSmartAutoplaying,
  setShowDirectUnmuteBanner,
  isPlayerVisible = true,
}: UseAutoplayProps) {
  const playSentRef = useRef(false)
  const autoplayStartedRef = useRef(false)

  useEffect(() => {
    if (!video || !isPlayerVisible || autoplayStartedRef.current) return
    const smart = video.player_settings?.smart_autoplay
    if (smart?.enabled) {
      autoplayStartedRef.current = true
      const isDirect = smart.mode === 'direct'
      if (isDirect) {
        setIsSmartAutoplaying(false)
        setIsMuted(false)
        if (videoRef.current) {
          videoRef.current.muted = false
          videoRef.current.volume = 1.0

          const attemptPlay = () => {
            if (!videoRef.current) return
            const p = videoRef.current.play()
            if (p && typeof p.then === 'function') {
              p.then(() => {
                setIsPlaying(true)
                if (!playSentRef.current) {
                  playSentRef.current = true
                  sendTelemetryEvent(videoId, { event_type: 'play', session_id: visitorId })
                }
              }).catch(() => {
                if (videoRef.current) {
                  videoRef.current.muted = true
                  setIsMuted(true)
                  setShowDirectUnmuteBanner(true)
                  videoRef.current.play().then(() => setIsPlaying(true)).catch(() => {})

                  const unlockAudio = () => {
                    if (videoRef.current) {
                      videoRef.current.muted = false
                      videoRef.current.volume = 1.0
                      setIsMuted(false)
                      setShowDirectUnmuteBanner(false)
                    }
                    if (!playSentRef.current) {
                      playSentRef.current = true
                      sendTelemetryEvent(videoId, { event_type: 'play', session_id: visitorId })
                    }
                    cleanupListeners()
                  }

                  const handleParentMsg = (e: MessageEvent) => {
                    if (e.data?.type === 'VTURB_PARENT_INTERACTION') {
                      unlockAudio()
                    }
                  }

                  const cleanupListeners = () => {
                    ;['click', 'touchstart', 'scroll', 'keydown', 'pointerdown'].forEach((evt) => {
                      window.removeEventListener(evt, unlockAudio)
                      document.removeEventListener(evt, unlockAudio)
                    })
                    window.removeEventListener('message', handleParentMsg)
                  }

                  ;['click', 'touchstart', 'scroll', 'keydown', 'pointerdown'].forEach((evt) => {
                    window.addEventListener(evt, unlockAudio, { once: true, passive: true })
                    document.addEventListener(evt, unlockAudio, { once: true, passive: true })
                  })
                  window.addEventListener('message', handleParentMsg, { once: true })
                }
              })
            } else {
              setIsPlaying(true)
              if (!playSentRef.current) {
                playSentRef.current = true
                sendTelemetryEvent(videoId, { event_type: 'play', session_id: visitorId })
              }
            }
          }

          try {
            attemptPlay()
          } catch {}
        }
      } else {
        setIsSmartAutoplaying(true)
        setIsMuted(true)
        if (videoRef.current) {
          videoRef.current.muted = true
          try {
            const p = videoRef.current.play()
            if (p && typeof p.then === 'function') {
              p.then(() => setIsPlaying(true)).catch(() => {})
            } else {
              setIsPlaying(true)
            }
          } catch {}
        }
      }
    }
  }, [video, videoId, visitorId, videoRef, setIsPlaying, setIsMuted, setIsSmartAutoplaying, setShowDirectUnmuteBanner, isPlayerVisible])
}
