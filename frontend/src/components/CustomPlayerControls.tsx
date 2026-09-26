import {
  Play,
  Pause,
  RotateCcw,
  RotateCw,
  Maximize,
} from 'lucide-react'
import { VolumeControl } from './VolumeControl'
import type { ChaptersSettings, PlayerControlsConfig, SmartProgressSettings } from '../types/video'
import { SMART_STRIP_CONTROLS_OFFSET } from './SmartProgressBar'
import { resolveSmartProgress } from '../utils/smartProgress'

interface CustomPlayerControlsProps {
  isPlaying: boolean
  isMuted: boolean
  volumeLevel?: number
  currentTime: number
  duration: number
  currentSpeed: number
  primaryColor: string
  controlsConfig?: PlayerControlsConfig
  chapters?: ChaptersSettings
  smartProgress?: SmartProgressSettings
  onTogglePlay: () => void
  onToggleMute: () => void
  onVolumeChange?: (val: number) => void
  onRewind10: () => void
  onForward10: () => void
  onCycleSpeed: () => void
  onToggleFullscreen: () => void
  onSeek: (seconds: number) => void
}

export const CustomPlayerControls: React.FC<CustomPlayerControlsProps> = ({
  isPlaying,
  isMuted,
  volumeLevel = 1.0,
  currentTime,
  duration,
  currentSpeed,
  primaryColor,
  controlsConfig = {},
  chapters,
  smartProgress,
  onTogglePlay,
  onToggleMute,
  onVolumeChange = () => {},
  onRewind10,
  onForward10,
  onCycleSpeed,
  onToggleFullscreen,
  onSeek,
}) => {
  const cfg = controlsConfig || {}
  const progressBar = cfg.progress_bar ?? true
  const videoTime = cfg.video_time ?? true
  const rewind10s = cfg.rewind_10s ?? true
  const forward10s = cfg.forward_10s ?? true
  const volume = cfg.volume ?? true
  const fullscreen = cfg.fullscreen ?? true
  const speedControl = cfg.speed_control ?? true

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60)
    const s = Math.floor(secs % 60)
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
  }

  const hasChapters = chapters?.enabled && chapters.items && chapters.items.length >= 2
  // Progresso Inteligente: a barra vira uma faixa na borda do player (SmartProgressStrip),
  // renderizada fora dos controles; aqui só reservamos o espaço dela embaixo
  const smartCfg = resolveSmartProgress(smartProgress)

  return (
    <div
      data-testid="embed-custom-controls"
      style={{
        position: 'absolute',
        bottom: 0,
        left: 0,
        right: 0,
        background: 'linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.4) 65%, transparent 100%)',
        padding: '0.5rem 0.65rem',
        ...(smartCfg.enabled && progressBar ? { paddingBottom: SMART_STRIP_CONTROLS_OFFSET } : {}),
        display: 'flex',
        flexDirection: 'column',
        gap: '0.4rem',
        zIndex: 15,
        transition: 'opacity 0.2s ease',
      }}
      onClick={(e) => e.stopPropagation()}
    >
      {/* Barra de Progresso (Segmentada por Capítulos se ativo, ou Contínua) */}
      {progressBar && !smartCfg.enabled && (
        hasChapters ? (
          <div
            data-testid="embed-chapters-progress-bar"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '3px',
              width: '100%',
              height: '6px',
              cursor: 'pointer',
              padding: '2px 0',
            }}
          >
            {[...chapters!.items]
              .sort((a, b) => a.seconds - b.seconds)
              .map((chap, idx, arr) => {
                const start = Math.max(0, chap.seconds)
                const end = idx < arr.length - 1
                  ? Math.max(start + 1, arr[idx + 1].seconds)
                  : Math.max(start + 1, duration || 60)
                const segDur = Math.max(0.1, end - start)
                const segWidth = (segDur / (duration || 60)) * 100
                let fillPct = 0
                if (currentTime >= end) fillPct = 100
                else if (currentTime > start) fillPct = ((currentTime - start) / segDur) * 100

                return (
                  <div
                    key={chap.id || idx}
                    data-testid={`embed-chapter-segment-${idx}`}
                    title={`${chap.title || `Capítulo ${idx + 1}`} (${chap.time})`}
                    onClick={() => onSeek(start)}
                    style={{
                      flex: `${segWidth} 0 0`,
                      height: '4px',
                      backgroundColor: 'rgba(255,255,255,0.25)',
                      borderRadius: '2px',
                      position: 'relative',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        width: `${fillPct}%`,
                        height: '100%',
                        backgroundColor: primaryColor,
                        borderRadius: '2px',
                      }}
                    />
                  </div>
                )
              })}
          </div>
        ) : (
          <input
            type="range"
            data-testid="embed-progress-bar"
            min="0"
            max={duration || 60}
            step="0.1"
            value={currentTime}
            onChange={(e) => onSeek(parseFloat(e.target.value))}
            style={{
              width: '100%',
              height: '4px',
              accentColor: primaryColor,
              cursor: 'pointer',
            }}
          />
        )
      )}

      {/* Linha de Controles Inferiores */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: '#ffffff', gap: '0.35rem', width: '100%' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flexShrink: 1, minWidth: 0, overflow: 'hidden' }}>
          {/* Botão Play / Pause */}
          <button
            type="button"
            data-testid="embed-control-play"
            onClick={onTogglePlay}
            style={{ background: 'transparent', border: 'none', color: '#ffffff', cursor: 'pointer', padding: '2px', display: 'flex', alignItems: 'center', flexShrink: 0 }}
            title={isPlaying ? 'Pausar' : 'Reproduzir'}
          >
            {isPlaying ? <Pause size={17} /> : <Play size={17} fill="#ffffff" />}
          </button>

          {/* Voltar 10s */}
          {rewind10s && (
            <button
              type="button"
              data-testid="embed-control-rewind"
              onClick={onRewind10}
              title="Voltar 10 segundos"
              style={{
                background: 'transparent',
                border: 'none',
                color: '#ffffff',
                cursor: 'pointer',
                fontSize: '0.72rem',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: '1px',
                padding: '2px',
                flexShrink: 0,
              }}
            >
              <RotateCcw size={14} />
              <span>10s</span>
            </button>
          )}

          {/* Avançar 10s */}
          {forward10s && (
            <button
              type="button"
              data-testid="embed-control-forward"
              onClick={onForward10}
              title="Avançar 10 segundos"
              style={{
                background: 'transparent',
                border: 'none',
                color: '#ffffff',
                cursor: 'pointer',
                fontSize: '0.72rem',
                fontWeight: 700,
                display: 'flex',
                alignItems: 'center',
                gap: '1px',
                padding: '2px',
                flexShrink: 0,
              }}
            >
              <span>10s</span>
              <RotateCw size={14} />
            </button>
          )}

          {/* Controle Interativo de Volume com Slider Popup */}
          {volume && (
            <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>
              <VolumeControl
                volume={volumeLevel}
                isMuted={isMuted}
                primaryColor={primaryColor}
                onVolumeChange={onVolumeChange}
                onToggleMute={onToggleMute}
                testIdPrefix="embed"
              />
            </div>
          )}

          {/* Tempo Restante do Vídeo */}
          {videoTime && (
            <span
              data-testid="embed-video-time"
              title="Tempo restante do vídeo"
              style={{
                fontSize: '0.74rem',
                color: '#cbd5e1',
                marginLeft: '0.2rem',
                fontFamily: 'monospace',
                fontWeight: 600,
                whiteSpace: 'nowrap',
                flexShrink: 1,
              }}
            >
              -{formatTime(Math.max(0, (duration || 0) - currentTime))}
            </span>
          )}
        </div>

        {/* Lado Direito: Velocidade e Fullscreen (Nunca encolhem) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', flexShrink: 0 }}>
          {speedControl && (
            <button
              type="button"
              data-testid="embed-control-speed"
              onClick={onCycleSpeed}
              title="Alterar Velocidade"
              style={{
                background: 'rgba(255,255,255,0.15)',
                border: '1px solid rgba(255,255,255,0.25)',
                color: '#ffffff',
                borderRadius: '4px',
                padding: '1px 5px',
                fontSize: '0.74rem',
                fontWeight: 700,
                cursor: 'pointer',
                flexShrink: 0,
              }}
            >
              {currentSpeed.toFixed(2)}x
            </button>
          )}

          {fullscreen && (
            <button
              type="button"
              data-testid="embed-control-fullscreen"
              onClick={onToggleFullscreen}
              title="Tela Cheia"
              style={{ background: 'transparent', border: 'none', color: '#ffffff', cursor: 'pointer', padding: '2px', display: 'flex', alignItems: 'center', flexShrink: 0 }}
            >
              <Maximize size={17} />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
