import React from 'react'
import type { ChapterItem, ChaptersSettings, SmartProgressSettings } from '../types/video'
import { mapChapterSegments, resolveSmartProgress, toVisualFraction } from '../utils/smartProgress'

/** Espessura da faixa na borda inferior do player (acompanha o tamanho do player). */
export const SMART_STRIP_HEIGHT = 'clamp(6px, 3.5%, 16px)'
/**
 * Espaço que os controles reservam embaixo para não ficarem em cima da faixa.
 * Usa a espessura máxima: % em padding é relativo à largura, não à altura do player.
 */
export const SMART_STRIP_CONTROLS_OFFSET = 'calc(16px + 0.35rem)'

interface SmartProgressBaseProps {
  testId: string
  currentTime: number
  duration: number
  settings: SmartProgressSettings
  primaryColor: string
}

const fillStyle = (widthPct: number, color: string): React.CSSProperties => ({
  width: `${widthPct}%`,
  height: '100%',
  backgroundColor: color,
  opacity: 0.85,
  transition: 'width 250ms linear',
})

/** Barra do Progresso Inteligente: só o preenchimento, sem trilho, sem arrastar nem clicar. */
export const SmartProgressBar: React.FC<SmartProgressBaseProps> = ({
  testId,
  currentTime,
  duration,
  settings,
  primaryColor,
}) => {
  const pct = Math.round(toVisualFraction(currentTime, duration, settings) * 1000) / 10

  return (
    <div
      data-testid={testId}
      role="progressbar"
      aria-label="Progresso do vídeo"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      style={{ width: '100%', height: '100%' }}
    >
      <div data-testid={`${testId.replace(/-bar$/, '')}-fill`} style={fillStyle(pct, primaryColor)} />
    </div>
  )
}

interface SmartChaptersBarProps extends SmartProgressBaseProps {
  segmentTestIdPrefix: string
  items: ChapterItem[]
}

/** Capítulos com o Progresso Inteligente: limites e preenchimento seguem a curva; sem navegação. */
export const SmartChaptersBar: React.FC<SmartChaptersBarProps> = ({
  testId,
  segmentTestIdPrefix,
  items,
  currentTime,
  duration,
  settings,
  primaryColor,
}) => {
  const sorted = [...items].sort((a, b) => a.seconds - b.seconds)
  const segments = mapChapterSegments(sorted, duration, currentTime, settings)

  return (
    <div data-testid={testId} style={{ display: 'flex', gap: '2px', width: '100%', height: '100%' }}>
      {sorted.map((chap, idx) => (
        <div
          key={chap.id || idx}
          data-testid={`${segmentTestIdPrefix}${idx}`}
          title={chap.title || `Capítulo ${idx + 1}`}
          style={{
            flex: `${segments[idx].widthPct} 0 0`,
            height: '100%',
            // Trilho leve só para marcar onde cada capítulo divide
            backgroundColor: 'rgba(255,255,255,0.18)',
            overflow: 'hidden',
          }}
        >
          <div style={fillStyle(segments[idx].fillPct, primaryColor)} />
        </div>
      ))}
    </div>
  )
}

const TEST_IDS = {
  embed: {
    strip: 'embed-smart-progress-strip',
    bar: 'embed-smart-progress-bar',
    chapters: 'embed-chapters-progress-bar',
    segment: 'embed-chapter-segment-',
  },
  styling: {
    strip: 'styling-smart-progress-strip',
    bar: 'smart-progress-bar',
    chapters: 'styling-chapters-progress-bar',
    segment: 'chapter-segment-',
  },
} as const

interface SmartProgressStripProps {
  idPrefix: keyof typeof TEST_IDS
  currentTime: number
  duration: number
  settings?: SmartProgressSettings
  primaryColor: string
  chapters?: ChaptersSettings
  progressBar?: boolean
}

/**
 * Faixa do Progresso Inteligente (estilo VTurb): colada na borda inferior do player,
 * de ponta a ponta, fora dos controles para continuar visível quando eles somem.
 * Não intercepta cliques (o clique cai no vídeo).
 */
export const SmartProgressStrip: React.FC<SmartProgressStripProps> = ({
  idPrefix,
  currentTime,
  duration,
  settings,
  primaryColor,
  chapters,
  progressBar = true,
}) => {
  const cfg = resolveSmartProgress(settings)
  if (!cfg.enabled || !progressBar) return null

  const ids = TEST_IDS[idPrefix]
  const hasChapters = !!chapters?.enabled && (chapters.items?.length ?? 0) >= 2

  return (
    <div
      data-testid={ids.strip}
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        bottom: 0,
        height: SMART_STRIP_HEIGHT,
        pointerEvents: 'none',
        zIndex: 16,
      }}
    >
      {hasChapters ? (
        <SmartChaptersBar
          testId={ids.chapters}
          segmentTestIdPrefix={ids.segment}
          items={chapters!.items}
          currentTime={currentTime}
          duration={duration}
          settings={cfg}
          primaryColor={primaryColor}
        />
      ) : (
        <SmartProgressBar
          testId={ids.bar}
          currentTime={currentTime}
          duration={duration}
          settings={cfg}
          primaryColor={primaryColor}
        />
      )}
    </div>
  )
}
