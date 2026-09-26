import React from 'react'
import {
  Play,
  Pause,
  RotateCcw,
  RotateCw,
  Maximize,
} from 'lucide-react'
import { VolumeControl } from '../../VolumeControl'
import type { ChaptersSettings, SmartProgressSettings } from '../../../types/video'
import { StylingProgressBar } from './StylingProgressBar'
import { formatTime } from './stylingPreviewHelpers'
import { SMART_STRIP_CONTROLS_OFFSET } from '../../SmartProgressBar'
import { resolveSmartProgress } from '../../../utils/smartProgress'

interface StylingPlayerControlsBarProps {
  progressBar?: boolean
  chapters?: ChaptersSettings
  smartProgress?: SmartProgressSettings
  duration: number
  currentTime: number
  primaryColor: string
  isPlaying: boolean
  rewind10s: boolean
  forward10s: boolean
  volume: boolean
  fullscreen: boolean
  speedControl: boolean
  videoTime?: boolean
  volumeLevel: number
  isMuted: boolean
  currentSpeed: number
  onTogglePlay: () => void
  onSeek: (e: React.ChangeEvent<HTMLInputElement>) => void
  onChapterClick: (start: number) => void
  onRewind10: () => void
  onForward10: () => void
  onVolumeChange: (val: number) => void
  onToggleMute: () => void
  onCycleSpeed: () => void
  onToggleFullscreen: () => void
}

export const StylingPlayerControlsBar: React.FC<StylingPlayerControlsBarProps> = ({
  progressBar = true,
  chapters,
  smartProgress,
  duration,
  currentTime,
  primaryColor,
  isPlaying,
  rewind10s,
  forward10s,
  volume,
  fullscreen,
  speedControl,
  videoTime = true,
  volumeLevel,
  isMuted,
  currentSpeed,
  onTogglePlay,
  onSeek,
  onChapterClick,
  onRewind10,
  onForward10,
  onVolumeChange,
  onToggleMute,
  onCycleSpeed,
  onToggleFullscreen,
}) => {
  return (
    <div
      data-testid="styling-player-controls-bar"
      style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        background: 'linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.4) 65%, transparent 100%)',
        padding: '0.75rem 1rem',
        ...(progressBar && resolveSmartProgress(smartProgress).enabled
          ? { paddingBottom: SMART_STRIP_CONTROLS_OFFSET }
          : {}),
        display: 'flex',
        flexDirection: 'column',
        gap: '0.45rem',
        transition: 'opacity 0.2s ease',
      }}
    >
      <StylingProgressBar
        progressBar={progressBar}
        chapters={chapters}
        smartProgress={smartProgress}
        duration={duration}
        currentTime={currentTime}
        primaryColor={primaryColor}
        onSeek={onSeek}
        onChapterClick={onChapterClick}
      />

      {/* Linha de Controles */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: '#ffffff' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <button
            type="button"
            data-testid="preview-control-play"
            onClick={onTogglePlay}
            style={{ background: 'transparent', border: 'none', color: '#ffffff', cursor: 'pointer', padding: '4px', display: 'flex' }}
          >
            {isPlaying ? <Pause size={18} /> : <Play size={18} fill="#ffffff" />}
          </button>

          {rewind10s && (
            <button
              type="button"
              data-testid="preview-control-rewind"
              onClick={onRewind10}
              title="Voltar 10 segundos"
              style={{
                background: 'transparent',
                border: 'none',
                color: '#ffffff',
                cursor: 'pointer',
                fontSize: '0.75rem',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: '2px',
              }}
            >
              <RotateCcw size={15} />
              <span>10s</span>
            </button>
          )}

          {forward10s && (
            <button
              type="button"
              data-testid="preview-control-forward"
              onClick={onForward10}
              title="Avançar 10 segundos"
              style={{
                background: 'transparent',
                border: 'none',
                color: '#ffffff',
                cursor: 'pointer',
                fontSize: '0.75rem',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: '2px',
              }}
            >
              <span>10s</span>
              <RotateCw size={15} />
            </button>
          )}

          {volume && (
            <VolumeControl
              volume={volumeLevel}
              isMuted={isMuted}
              primaryColor={primaryColor}
              onVolumeChange={onVolumeChange}
              onToggleMute={onToggleMute}
              testIdPrefix="preview"
            />
          )}

          {videoTime && (
            <span
              data-testid="styling-video-time"
              title="Tempo restante para acabar o vídeo"
              style={{
                fontSize: '0.78rem',
                color: '#cbd5e1',
                marginLeft: '0.35rem',
                fontFamily: 'monospace',
                fontWeight: 600,
              }}
            >
              -{formatTime(Math.max(0, (duration || 0) - currentTime))}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          {speedControl && (
            <button
              type="button"
              data-testid="preview-control-speed"
              onClick={onCycleSpeed}
              title="Alterar Velocidade"
              style={{
                background: 'rgba(255,255,255,0.15)',
                border: '1px solid rgba(255,255,255,0.25)',
                color: '#ffffff',
                borderRadius: '5px',
                padding: '2px 7px',
                fontSize: '0.78rem',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              {currentSpeed.toFixed(2)}x
            </button>
          )}

          {fullscreen && (
            <button
              type="button"
              data-testid="preview-control-fullscreen"
              onClick={onToggleFullscreen}
              title="Tela Cheia"
              style={{ background: 'transparent', border: 'none', color: '#ffffff', cursor: 'pointer', padding: '4px', display: 'flex' }}
            >
              <Maximize size={18} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
