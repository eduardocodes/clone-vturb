import React from 'react'
import type { ChaptersSettings, SmartProgressSettings } from '../../../types/video'
import { resolveSmartProgress } from '../../../utils/smartProgress'

interface StylingProgressBarProps {
  progressBar?: boolean
  chapters?: ChaptersSettings
  duration: number
  currentTime: number
  primaryColor: string
  smartProgress?: SmartProgressSettings
  onSeek: (e: React.ChangeEvent<HTMLInputElement>) => void
  onChapterClick: (start: number) => void
}

export const StylingProgressBar: React.FC<StylingProgressBarProps> = ({
  progressBar = true,
  chapters,
  duration,
  currentTime,
  primaryColor,
  smartProgress,
  onSeek,
  onChapterClick,
}) => {
  if (!progressBar) return null

  // Progresso Inteligente: a faixa é desenhada pelo container da prévia (SmartProgressStrip)
  if (resolveSmartProgress(smartProgress).enabled) return null

  if (chapters?.enabled && chapters.items.length >= 2) {
    const sortedChapters = [...chapters.items].sort((a, b) => a.seconds - b.seconds)

    return (
      <div
        data-testid="styling-chapters-progress-bar"
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
        {sortedChapters.map((chap, idx, arr) => {
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
              data-testid={`chapter-segment-${idx}`}
              title={`${chap.title || `Capítulo ${idx + 1}`} (${chap.time})`}
              onClick={() => onChapterClick(start)}
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
    )
  }

  return (
    <input
      type="range"
      data-testid="styling-progress-bar"
      min="0"
      max={duration || 60}
      value={currentTime}
      onChange={onSeek}
      style={{
        width: '100%',
        height: '4px',
        accentColor: primaryColor,
        cursor: 'pointer',
      }}
    />
  )
}
