import React, { useEffect, useRef, useState } from 'react'
import { Loader2, AlertTriangle, RotateCcw } from 'lucide-react'
import type { Video } from '../types/video'

interface VideoProcessingBadgeProps {
  video: Video
  /** Reprocessar (só aparece em vídeo com falha) */
  onReprocess?: (video: Video) => Promise<void>
  /** Recebe o vídeo atualizado quando o processamento termina (com fetchVideo) */
  onChange?: (video: Video) => void
  fetchVideo?: (id: string) => Promise<Video>
  pollMs?: number
}

/** Status do processamento HLS: "Processando" (o MP4 original segue tocando) ou "Falhou". */
export const VideoProcessingBadge: React.FC<VideoProcessingBadgeProps> = ({
  video,
  onReprocess,
  onChange,
  fetchVideo,
  pollMs = 10_000,
}) => {
  const [busy, setBusy] = useState(false)
  const onChangeRef = useRef(onChange)
  const fetchRef = useRef(fetchVideo)

  useEffect(() => {
    onChangeRef.current = onChange
    fetchRef.current = fetchVideo
  })

  const processing = video.status === 'processing'
  const polling = processing && Boolean(fetchVideo && onChange)

  useEffect(() => {
    if (!polling) return
    let cancelled = false
    const timer = setInterval(async () => {
      try {
        const fresh = await fetchRef.current!(video.id)
        if (!cancelled && fresh.status !== 'processing') onChangeRef.current?.(fresh)
      } catch {
        // Falha de rede: tenta de novo no próximo intervalo
      }
    }, pollMs)
    return () => {
      cancelled = true
      clearInterval(timer)
    }
  }, [polling, video.id, pollMs])

  if (video.status !== 'processing' && video.status !== 'failed') return null

  const failed = video.status === 'failed'
  const title = failed
    ? `O processamento para streaming falhou${video.processing_error ? `: ${video.processing_error}` : ''}. O player segue usando o arquivo original.`
    : 'Gerando as versões para streaming (HLS). Enquanto isso, o player usa o arquivo original.'

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
      <span
        data-testid={`video-processing-badge-${video.id}`}
        title={title}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.3rem',
          padding: '0.15rem 0.5rem',
          borderRadius: '999px',
          fontSize: '0.72rem',
          fontWeight: 600,
          background: failed ? '#fee2e2' : '#fef3c7',
          color: failed ? '#b91c1c' : '#92400e',
          whiteSpace: 'nowrap',
        }}
      >
        {failed ? <AlertTriangle size={12} /> : <Loader2 size={12} className="animate-spin" style={{ animation: 'spin 1s linear infinite' }} />}
        {failed ? 'Falhou' : 'Processando'}
      </span>
      {failed && onReprocess && (
        <button
          type="button"
          data-testid={`video-reprocess-btn-${video.id}`}
          disabled={busy}
          onClick={async () => {
            setBusy(true)
            try {
              await onReprocess(video)
            } finally {
              setBusy(false)
            }
          }}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.25rem',
            border: '1px solid #e2e8f0',
            background: '#ffffff',
            color: '#334155',
            borderRadius: '6px',
            padding: '0.15rem 0.5rem',
            fontSize: '0.72rem',
            cursor: busy ? 'wait' : 'pointer',
          }}
        >
          <RotateCcw size={12} /> Reprocessar
        </button>
      )}
    </span>
  )
}
