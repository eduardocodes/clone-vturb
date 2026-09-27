import { useState, useRef, useEffect } from 'react'
import type { Video } from '../../types/video'
import { sendTelemetryEvent } from '../../services/api'
import { useAutoplay } from '../../hooks/useAutoplay'
import { useVideoTelemetry } from '../../hooks/useVideoTelemetry'
import { isElementCurrentlyVisible } from './embedPlayerHelpers'

interface UseEmbedPlaybackOptions {
  video: Video | null
  videoId: string
  visitorId: string
  videoRef: React.RefObject<HTMLVideoElement | null>
  containerRef: React.RefObject<HTMLDivElement | null>
  setIsVideoReady: (ready: boolean) => void
  isVideoReady: boolean
}

export function useEmbedPlayback({
  video,
  videoId,
  visitorId,
  videoRef,
  containerRef,
  setIsVideoReady,
  isVideoReady,
}: UseEmbedPlaybackOptions) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [volumeLevel, setVolumeLevel] = useState(1.0)
  const [showCta, setShowCta] = useState(false)
  const [isSmartAutoplaying, setIsSmartAutoplaying] = useState(false)
  const [showDirectUnmuteBanner, setShowDirectUnmuteBanner] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [currentSpeed, setCurrentSpeed] = useState(1.0)
  const [areControlsVisible, setAreControlsVisible] = useState(true)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [isPlayerVisible, setIsPlayerVisible] = useState<boolean>(() =>
    isElementCurrentlyVisible(containerRef.current)
  )

  const controlsTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { trackImpression, handleTimeUpdateProgress, handleEndedTelemetry } = useVideoTelemetry({
    video,
    videoId,
    visitorId,
    setShowCta,
  })

  // Monitora se o player/iframe está realmente visível na tela (evita disparo oculto em etapas anteriores de Quiz)
  useEffect(() => {
    const checkVisibility = () => {
      if (isElementCurrentlyVisible(containerRef.current)) {
        setIsPlayerVisible(true)
      }
    }
    checkVisibility()

    const handleMsg = (e: MessageEvent) => {
      if (e.data?.type === 'VTURB_VISIBILITY' && typeof e.data.visible === 'boolean') {
        if (e.data.visible) setIsPlayerVisible(true)
      }
    }

    window.addEventListener('resize', checkVisibility)
    document.addEventListener('visibilitychange', checkVisibility)
    window.addEventListener('message', handleMsg)

    let observer: IntersectionObserver | null = null
    if (typeof IntersectionObserver !== 'undefined' && containerRef.current) {
      observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting && isElementCurrentlyVisible(containerRef.current)) {
            setIsPlayerVisible(true)
          }
        })
      }, { threshold: 0.05 })
      observer.observe(containerRef.current)
    }

    return () => {
      window.removeEventListener('resize', checkVisibility)
      document.removeEventListener('visibilitychange', checkVisibility)
      window.removeEventListener('message', handleMsg)
      observer?.disconnect()
    }
  }, [video, containerRef])

  // Aplica velocidade Turbo configurada no vídeo se turbo_enabled for true
  useEffect(() => {
    if (videoRef.current) {
      const isTurbo = Boolean(video?.player_settings?.turbo_enabled)
      const rate = Number(video?.player_settings?.playback_rate) || 1.0
      videoRef.current.playbackRate = isTurbo ? rate : 1.0
    }
  }, [video, videoRef])

  // Inicializa Autoplay via Hook customizado apenas quando o player estiver visível
  useAutoplay({
    video,
    videoId,
    visitorId,
    videoRef,
    setIsPlaying,
    setIsMuted,
    setIsSmartAutoplaying,
    setShowDirectUnmuteBanner,
    isPlayerVisible,
  })

  useEffect(() => {
    const onFs = () => setIsFullscreen(Boolean(document.fullscreenElement))
    document.addEventListener('fullscreenchange', onFs)
    return () => document.removeEventListener('fullscreenchange', onFs)
  }, [])

  const resetControlsVisibilityTimeout = () => {
    setAreControlsVisible(true)
    if (controlsTimeoutRef.current) clearTimeout(controlsTimeoutRef.current)
    controlsTimeoutRef.current = setTimeout(() => {
      if (isPlaying) setAreControlsVisible(false)
    }, 3500)
  }

  const handleTimeUpdate = () => {
    if (!videoRef.current || !video) return
    const current = videoRef.current.currentTime
    const total = videoRef.current.duration || video.duration || 0
    setCurrentTime(current)
    if (total > 0 && total !== duration) setDuration(total)
    if (current > 0.05 && !isVideoReady) setIsVideoReady(true)
    const isSmartMutedPreview =
      isSmartAutoplaying ||
      Boolean(
        video.player_settings?.smart_autoplay?.enabled &&
          video.player_settings?.smart_autoplay?.mode !== 'direct' &&
          videoRef.current.muted
      )
    handleTimeUpdateProgress(current, total, isSmartMutedPreview)
  }

  const handlePlay = () => {
    if (videoRef.current) {
      if (video?.player_settings?.playback_rate) {
        videoRef.current.playbackRate = Number(video.player_settings.playback_rate) || 1.0
      }
      videoRef.current.play().catch(() => {})
      setIsPlaying(true)
      sendTelemetryEvent(videoId, { event_type: 'play', session_id: visitorId })
    }
  }

  const handleSmartAutoplayUnmute = () => {
    if (!videoRef.current) return
    const smart = video?.player_settings?.smart_autoplay
    videoRef.current.muted = false
    setIsMuted(false)
    if (smart?.restart_on_unmute) videoRef.current.currentTime = 0
    videoRef.current.play().catch(() => {})
    setIsPlaying(true)
    setIsSmartAutoplaying(false)
    sendTelemetryEvent(videoId, { event_type: 'play', session_id: visitorId })
  }

  const handleTogglePlay = () => {
    if (!videoRef.current) return
    if (videoRef.current.paused) {
      videoRef.current.play().then(() => setIsPlaying(true)).catch(() => {})
      sendTelemetryEvent(videoId, { event_type: 'play', session_id: visitorId })
    } else {
      videoRef.current.pause()
      setIsPlaying(false)
    }
  }

  const handleToggleMute = () => {
    if (!videoRef.current) return
    const next = !videoRef.current.muted
    videoRef.current.muted = next
    setIsMuted(next)
    if (!next && videoRef.current.volume === 0) {
      videoRef.current.volume = 1.0
      setVolumeLevel(1.0)
    }
  }

  const handleVolumeChange = (newVal: number) => {
    if (!videoRef.current) return
    videoRef.current.volume = newVal
    setVolumeLevel(newVal)
    if (newVal === 0) {
      videoRef.current.muted = true
      setIsMuted(true)
    } else if (isMuted) {
      videoRef.current.muted = false
      setIsMuted(false)
    }
  }

  const handleRewind10 = () => {
    if (!videoRef.current) return
    const next = Math.max(0, videoRef.current.currentTime - 10)
    videoRef.current.currentTime = next
    setCurrentTime(next)
  }

  const handleForward10 = () => {
    if (!videoRef.current) return
    const maxDur = duration || video?.duration || 60
    const next = Math.min(maxDur, videoRef.current.currentTime + 10)
    videoRef.current.currentTime = next
    setCurrentTime(next)
  }

  const handleSeek = (seconds: number) => {
    if (!videoRef.current) return
    videoRef.current.currentTime = seconds
    setCurrentTime(seconds)
  }

  const handleCycleSpeed = () => {
    const speeds = [1.0, 1.25, 1.5, 2.0]
    const next = speeds[(speeds.indexOf(currentSpeed) + 1) % speeds.length]
    setCurrentSpeed(next)
    if (videoRef.current) videoRef.current.playbackRate = next
  }

  const handleToggleFullscreen = () => {
    if (!containerRef.current) return
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().catch(() => {})
    } else {
      document.exitFullscreen().catch(() => {})
    }
  }

  const handleDirectUnmute = () => {
    if (videoRef.current) {
      videoRef.current.muted = false
      videoRef.current.volume = 1.0
      setIsMuted(false)
      setShowDirectUnmuteBanner(false)
      videoRef.current.play().catch(() => {})
      sendTelemetryEvent(videoId, { event_type: 'play', session_id: visitorId })
    }
  }

  const handleEnded = () => handleEndedTelemetry(videoRef.current?.duration || 0, isSmartAutoplaying)
  const handleCtaClick = () => sendTelemetryEvent(videoId, { event_type: 'click', session_id: visitorId })

  return {
    isPlaying,
    setIsPlaying,
    isMuted,
    setIsMuted,
    volumeLevel,
    setVolumeLevel,
    showCta,
    isSmartAutoplaying,
    showDirectUnmuteBanner,
    setShowDirectUnmuteBanner,
    currentTime,
    duration,
    currentSpeed,
    areControlsVisible,
    setAreControlsVisible,
    isFullscreen,
    isPlayerVisible,
    trackImpression,
    resetControlsVisibilityTimeout,
    handleTimeUpdate,
    handlePlay,
    handleSmartAutoplayUnmute,
    handleTogglePlay,
    handleToggleMute,
    handleVolumeChange,
    handleRewind10,
    handleForward10,
    handleSeek,
    handleCycleSpeed,
    handleToggleFullscreen,
    handleDirectUnmute,
    handleEnded,
    handleCtaClick,
  }
}
