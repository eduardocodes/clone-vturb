import React, { useEffect, useRef, useState } from 'react'
import type { Video } from '../types/video'
import { fetchVideo, getMediaUrl } from '../services/api'
import { SmartAutoplayOverlay } from './SmartAutoplayOverlay'
import { BigPlayOverlay } from './BigPlayOverlay'
import { DirectUnmuteBanner } from './DirectUnmuteBanner'
import { CustomPlayerControls } from './CustomPlayerControls'
import { SmartProgressStrip } from './SmartProgressBar'
import { CtaButtonOverlay } from './CtaButtonOverlay'
import { useDomainProtection } from '../hooks/useDomainProtection'
import { EmbedLoadingState, EmbedErrorState, EmbedBlockedState } from './EmbedPlayerStates'
import {
  EmbedBufferingOverlay,
  EmbedFloatingCloseButton,
  useEmbedTransparency,
  useEmbedFloatingPlayer,
  useEmbedPlayback,
  getOrCreateVisitorId,
  parseEmbedDimensions,
  computeEmbedContainerStyle,
} from './embed'

interface EmbedPlayerProps {
  videoId: string
}

export const EmbedPlayer: React.FC<EmbedPlayerProps> = ({ videoId }) => {
  const [video, setVideo] = useState<Video | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [visitorId] = useState(getOrCreateVisitorId)

  const containerRef = useRef<HTMLDivElement | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)

  const domainBlocked = useDomainProtection(video)
  const { effectiveRatio, configuredWidth, isTransparent, isInsideIframe } = parseEmbedDimensions(video)

  const { isVideoReady, setIsVideoReady } = useEmbedTransparency({
    video,
    videoRef,
    isTransparent,
  })

  const {
    isPlaying,
    setIsPlaying,
    isMuted,
    volumeLevel,
    showCta,
    isSmartAutoplaying,
    showDirectUnmuteBanner,
    currentTime,
    duration,
    currentSpeed,
    areControlsVisible,
    isFullscreen,
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
  } = useEmbedPlayback({
    video,
    videoId,
    visitorId,
    videoRef,
    containerRef,
    setIsVideoReady,
    isVideoReady,
  })

  const {
    isFloatingActive,
    floatingConfig,
    handleDismissFloating,
  } = useEmbedFloatingPlayer({
    video,
    videoId,
    isPlaying,
    setIsPlaying,
    containerRef,
    videoRef,
    isInsideIframe,
  })

  useEffect(() => {
    async function init() {
      try {
        setLoading(true)
        const data = await fetchVideo(videoId)
        setVideo(data)
        trackImpression()
      } catch (err: any) {
        setError('Vídeo indisponível ou excluído.')
      } finally {
        setLoading(false)
      }
    }
    init()
  }, [videoId, visitorId])

  if (loading) return <EmbedLoadingState />
  if (error || !video) return <EmbedErrorState error={error} />
  if (domainBlocked) return <EmbedBlockedState />

  const primaryColor = video.player_settings?.primary_color || '#6366f1'
  const antiDownloadActive = video.player_settings?.domain_protection?.anti_download !== false

  const containerStyle = computeEmbedContainerStyle({
    isFloatingActive,
    isFullscreen,
    isTransparent,
    isVideoReady,
    floatingConfig,
    effectiveRatio,
    configuredWidth,
    isInsideIframe,
    borderRadius: video.player_settings?.border_radius,
  })

  return (
    <div
      ref={containerRef}
      data-testid="vturb-embed-player"
      onContextMenu={(e) => {
        if (antiDownloadActive) e.preventDefault()
      }}
      onMouseEnter={resetControlsVisibilityTimeout}
      onMouseMove={resetControlsVisibilityTimeout}
      onMouseLeave={() => {
        if (isPlaying) resetControlsVisibilityTimeout()
      }}
      style={containerStyle}
    >
      <EmbedFloatingCloseButton
        isFloatingActive={isFloatingActive}
        closeable={floatingConfig?.closeable}
        onClose={handleDismissFloating}
      />

      <EmbedBufferingOverlay
        isVideoReady={isVideoReady}
        primaryColor={primaryColor}
      />

      <video
        ref={videoRef}
        src={getMediaUrl(video.video_url)}
        poster={getMediaUrl(video.thumbnail_url)}
        controls={false}
        controlsList={antiDownloadActive ? 'nodownload' : undefined}
        preload="auto"
        onLoadedData={() => {
          if (videoRef.current && videoRef.current.readyState >= 2) {
            requestAnimationFrame(() => setIsVideoReady(true))
          }
        }}
        onCanPlay={() => {
          if (videoRef.current && videoRef.current.readyState >= 3) {
            setIsVideoReady(true)
          }
        }}
        onPlaying={() => {
          requestAnimationFrame(() => setIsVideoReady(true))
        }}
        onTimeUpdate={handleTimeUpdate}
        onEnded={handleEnded}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onClick={handleTogglePlay}
        style={{
          width: '100%',
          height: '100%',
          objectFit: isFullscreen || !isTransparent ? 'contain' : (video.player_settings?.fit_mode || 'contain'),
          cursor: 'pointer',
          backgroundColor: isFullscreen ? '#000000' : isTransparent && isVideoReady ? 'transparent' : '#000000',
        }}
        playsInline
      />

      {/* Barra de Controles Personalizada do Player (Respeita controles visuais e show_controls) */}
      {video.player_settings?.show_controls !== false && (isPlaying || areControlsVisible) && !isSmartAutoplaying && (
        <div
          style={{
            opacity: isPlaying && !areControlsVisible ? 0 : 1,
            pointerEvents: isPlaying && !areControlsVisible ? 'none' : 'auto',
            transition: 'opacity 0.25s ease',
          }}
        >
          <CustomPlayerControls
            isPlaying={isPlaying}
            isMuted={isMuted}
            volumeLevel={volumeLevel}
            currentTime={currentTime}
            duration={duration || video.duration || 60}
            currentSpeed={currentSpeed}
            primaryColor={primaryColor}
            controlsConfig={video.player_settings?.controls_config || undefined}
            chapters={video.player_settings?.chapters || undefined}
            smartProgress={video.player_settings?.smart_progress || undefined}
            onTogglePlay={handleTogglePlay}
            onToggleMute={handleToggleMute}
            onVolumeChange={handleVolumeChange}
            onRewind10={handleRewind10}
            onForward10={handleForward10}
            onCycleSpeed={handleCycleSpeed}
            onToggleFullscreen={handleToggleFullscreen}
            onSeek={handleSeek}
          />
        </div>
      )}

      {/* Progresso Inteligente: faixa na borda inferior, fora dos controles para ficar sempre visível */}
      {!isSmartAutoplaying && (
        <SmartProgressStrip
          idPrefix="embed"
          currentTime={currentTime}
          duration={duration || video.duration || 60}
          settings={video.player_settings?.smart_progress || undefined}
          primaryColor={primaryColor}
          chapters={video.player_settings?.chapters || undefined}
          progressBar={video.player_settings?.controls_config?.progress_bar ?? true}
        />
      )}

      {/* Smart Autoplay™ Overlay */}
      {isSmartAutoplaying && (
        <SmartAutoplayOverlay
          settings={video.player_settings?.smart_autoplay}
          onUnmute={handleSmartAutoplayUnmute}
        />
      )}

      {/* Banner Informativo Discreto de Autoplay Direto */}
      {showDirectUnmuteBanner && (
        <DirectUnmuteBanner
          buttonColor={video.player_settings?.smart_autoplay?.button_color || '#ef4444'}
          text={video.player_settings?.smart_autoplay?.text || 'Seu vídeo já começou!'}
          buttonText={video.player_settings?.smart_autoplay?.button_text || 'OUVIR'}
          onUnmute={handleDirectUnmute}
        />
      )}

      {/* Botão de Play Inteligente (Overlay Padrão) */}
      {!isPlaying && !isSmartAutoplaying && (
        <BigPlayOverlay
          primaryColor={primaryColor}
          shape={video.player_settings?.play_button_shape}
          size={video.player_settings?.play_button_size}
          onPlay={handlePlay}
        />
      )}

      {/* Botão de CTA com delay */}
      <CtaButtonOverlay
        show={showCta && Boolean(video.player_settings?.cta_enabled)}
        ctaLink={video.player_settings?.cta_link}
        ctaText={video.player_settings?.cta_text}
        onClick={handleCtaClick}
      />
    </div>
  )
}
