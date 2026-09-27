import React from 'react'
import { Play } from 'lucide-react'
import type { Video } from '../../../types/video'
import { getMediaUrl } from '../../../services/api'
import { getYCoordinate } from './retentionChartHelpers'

interface RetentionChartCanvasProps {
  chartRef: React.RefObject<HTMLDivElement | null>
  onMouseMove: (e: React.MouseEvent<HTMLDivElement>) => void
  video: Video
  activeAreaD: string
  activePathD: string
  showConversions: boolean
  ctrPercent: number
  ctaXPercent?: number
  ctaLabel?: string
  children: React.ReactNode
}

export const RetentionChartCanvas: React.FC<RetentionChartCanvasProps> = ({
  chartRef,
  onMouseMove,
  video,
  activeAreaD,
  activePathD,
  showConversions,
  ctrPercent,
  ctaXPercent,
  ctaLabel,
  children,
}) => {
  return (
    <div
      ref={chartRef}
      data-testid="vturb-chart-canvas"
      onMouseMove={onMouseMove}
      style={{
        flex: 1,
        position: 'relative',
        background: '#000000',
        borderRadius: '10px',
        overflow: 'hidden',
        cursor: 'crosshair',
        border: '1px solid rgba(255, 255, 255, 0.05)',
      }}
    >
      {/* Linhas de Grade Horizontais */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          padding: '15px 0 20px',
          pointerEvents: 'none',
        }}
      >
        <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.07)', width: '100%' }} />
        <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.07)', width: '100%' }} />
        <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.07)', width: '100%' }} />
        <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.07)', width: '100%' }} />
        <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.07)', width: '100%' }} />
        <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.07)', width: '100%' }} />
      </div>

      {/* Imagem Central do Vídeo Estilo VTurb */}
      <div
        data-testid="vturb-chart-video-thumbnail"
        style={{
          position: 'absolute',
          left: '50%',
          top: '10px',
          bottom: '20px',
          transform: 'translateX(-50%)',
          width: '160px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          overflow: 'hidden',
          borderRadius: '8px',
          boxShadow: '0 0 25px rgba(0, 0, 0, 0.9)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          zIndex: 1,
          pointerEvents: 'none',
        }}
      >
        {video.thumbnail_url ? (
          <img
            src={getMediaUrl(video.thumbnail_url)}
            alt={video.title}
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
              opacity: 0.95,
            }}
          />
        ) : (
          <div
            style={{
              width: '100%',
              height: '100%',
              background: 'linear-gradient(180deg, #1e293b 0%, #090d16 100%)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#94a3b8',
              padding: '0.75rem',
              textAlign: 'center',
            }}
          >
            <Play size={26} color="#10b981" />
            <span style={{ fontSize: '0.72rem', marginTop: '0.4rem', fontWeight: 600 }}>{video.title}</span>
          </div>
        )}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background:
              'linear-gradient(90deg, rgba(0,0,0,0.5) 0%, transparent 20%, transparent 80%, rgba(0,0,0,0.5) 100%)',
          }}
        />
      </div>

      {/* Curva SVG Neon de Retenção e Audiência */}
      <svg
        viewBox="0 0 1000 200"
        preserveAspectRatio="none"
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          zIndex: 2,
          pointerEvents: 'none',
        }}
      >
        <defs>
          <linearGradient id="neonGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#22c55e" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#22c55e" stopOpacity="0.0" />
          </linearGradient>
        </defs>
        <path d={activeAreaD} fill="url(#neonGradient)" />
        <path
          data-testid="vturb-neon-retention-curve"
          d={activePathD}
          fill="none"
          stroke="#22c55e"
          strokeWidth="2.5"
          style={{
            filter: 'drop-shadow(0 0 6px rgba(34, 197, 94, 0.75))',
          }}
        />
        {showConversions && (
          <line
            x1="0"
            y1={getYCoordinate(ctrPercent)}
            x2="1000"
            y2={getYCoordinate(ctrPercent)}
            stroke="#f59e0b"
            strokeWidth="1.5"
            strokeDasharray="4 4"
          />
        )}
        {ctaXPercent !== undefined && ctaXPercent > 0 && ctaXPercent <= 100 && (
          <line
            data-testid="chart-cta-marker-line"
            x1={ctaXPercent * 10}
            y1="0"
            x2={ctaXPercent * 10}
            y2="200"
            stroke="#f59e0b"
            strokeWidth="1.5"
            strokeDasharray="3 3"
            opacity="0.85"
          />
        )}
      </svg>

      {/* Badge Flutuante no Topo da Linha da Oferta */}
      {ctaXPercent !== undefined && ctaXPercent > 0 && ctaXPercent <= 100 && (
        <div
          data-testid="chart-cta-badge"
          style={{
            position: 'absolute',
            left: `${ctaXPercent}%`,
            top: '8px',
            transform: 'translateX(-50%)',
            background: 'rgba(245, 158, 11, 0.92)',
            color: '#ffffff',
            fontSize: '0.68rem',
            fontWeight: 800,
            padding: '0.15rem 0.45rem',
            borderRadius: '4px',
            zIndex: 3,
            boxShadow: '0 2px 8px rgba(245, 158, 11, 0.4)',
            pointerEvents: 'none',
            display: 'flex',
            alignItems: 'center',
            gap: '0.2rem',
            letterSpacing: '0.02em',
            whiteSpace: 'nowrap',
          }}
        >
          <span>🎯 Oferta {ctaLabel}</span>
        </div>
      )}

      {/* Scrubber e Tooltip passados como children */}
      {children}
    </div>
  )
}
