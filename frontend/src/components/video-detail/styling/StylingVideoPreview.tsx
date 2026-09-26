import React from 'react'
import type { Video, ChaptersSettings, SmartProgressSettings } from '../../../types/video'
import { getMediaUrl } from '../../../services/api'
import { StylingPreviewHeader } from './StylingPreviewHeader'
import { StylingBigPlayButton } from './StylingBigPlayButton'
import { StylingPlayerControlsBar } from './StylingPlayerControlsBar'
import { SmartProgressStrip } from '../../SmartProgressBar'
import { useStylingPreviewPlayer } from './useStylingPreviewPlayer'

interface StylingVideoPreviewProps {
  video: Video
  primaryColor: string
  playShape: 'circle' | 'rounded' | 'square' | 'minimal'
  playSize: 'small' | 'medium' | 'large'
  rewind10s: boolean
  forward10s: boolean
  volume: boolean
  fullscreen: boolean
  speedControl: boolean
  borderRadius?: number
  progressBar?: boolean
  videoTime?: boolean
  aspectRatio?: '16:9' | '9:16'
  onAspectRatioChange?: (val: '16:9' | '9:16') => void
  chapters?: ChaptersSettings
  smartProgress?: SmartProgressSettings
}

export const StylingVideoPreview: React.FC<StylingVideoPreviewProps> = ({
  video,
  primaryColor,
  playShape,
  playSize,
  rewind10s,
  forward10s,
  volume,
  fullscreen,
  speedControl,
  borderRadius = 0,
  progressBar = true,
  videoTime = true,
  aspectRatio = '16:9',
  onAspectRatioChange,
  chapters,
  smartProgress,
}) => {
  const {
    videoRef,
    containerRef,
    isPlaying,
    setIsPlaying,
    currentTime,
    duration,
    isMuted,
    volumeLevel,
    currentSpeed,
    togglePlay,
    handleTimeUpdate,
    handleSeek,
    handleChapterClick,
    handleRewind10,
    handleForward10,
    toggleMute,
    handleVolumeChange,
    cycleSpeed,
    toggleFullscreen,
  } = useStylingPreviewPlayer({ initialDuration: video.duration || 60 })

  return (
    <div
      style={{
        background: '#ffffff',
        border: '1px solid #e2e8f0',
        borderRadius: '16px',
        padding: '1.5rem',
        boxShadow: '0 4px 12px rgba(0,0,0,0.03)',
      }}
    >
      <StylingPreviewHeader
        aspectRatio={aspectRatio}
        onAspectRatioChange={onAspectRatioChange}
      />

      <div
        ref={containerRef}
        data-testid="styling-video-preview-container"
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: aspectRatio === '9:16' ? '340px' : '100%',
          aspectRatio: aspectRatio === '9:16' ? '9/16' : '16/9',
          margin: '0 auto',
          backgroundColor: '#0a0c10',
          borderRadius: `${borderRadius}px`,
          overflow: 'hidden',
          boxShadow: aspectRatio === '9:16'
            ? '0 14px 40px rgba(0,0,0,0.35), 0 0 0 6px #1e293b'
            : '0 8px 24px rgba(0,0,0,0.25)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        <video
          ref={videoRef}
          data-testid="styling-preview-video"
          src={getMediaUrl(video.video_url)}
          poster={getMediaUrl(video.thumbnail_url)}
          playsInline
          muted={isMuted}
          onTimeUpdate={handleTimeUpdate}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onClick={togglePlay}
          style={{ width: '100%', height: '100%', objectFit: 'contain', cursor: 'pointer' }}
        />

        <StylingBigPlayButton
          isPlaying={isPlaying}
          playShape={playShape}
          playSize={playSize}
          primaryColor={primaryColor}
          onTogglePlay={togglePlay}
        />

        <SmartProgressStrip
          idPrefix="styling"
          currentTime={currentTime}
          duration={duration}
          settings={smartProgress}
          primaryColor={primaryColor}
          chapters={chapters}
          progressBar={progressBar}
        />

        <StylingPlayerControlsBar
          progressBar={progressBar}
          chapters={chapters}
          smartProgress={smartProgress}
          duration={duration}
          currentTime={currentTime}
          primaryColor={primaryColor}
          isPlaying={isPlaying}
          rewind10s={rewind10s}
          forward10s={forward10s}
          volume={volume}
          fullscreen={fullscreen}
          speedControl={speedControl}
          videoTime={videoTime}
          volumeLevel={volumeLevel}
          isMuted={isMuted}
          currentSpeed={currentSpeed}
          onTogglePlay={togglePlay}
          onSeek={handleSeek}
          onChapterClick={handleChapterClick}
          onRewind10={handleRewind10}
          onForward10={handleForward10}
          onVolumeChange={handleVolumeChange}
          onToggleMute={toggleMute}
          onCycleSpeed={cycleSpeed}
          onToggleFullscreen={toggleFullscreen}
        />
      </div>
    </div>
  )
}
