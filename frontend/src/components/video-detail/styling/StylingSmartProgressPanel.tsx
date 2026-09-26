import React from 'react'
import { Gauge } from 'lucide-react'
import type { SmartProgressIntensity, SmartProgressSettings } from '../../../types/video'

interface StylingSmartProgressPanelProps {
  smartProgress: SmartProgressSettings
  onChange: (updated: SmartProgressSettings) => void
  progressBarVisible: boolean
}

const INTENSITY_OPTIONS: { id: SmartProgressIntensity; label: string; hint: string }[] = [
  { id: 'suave', label: 'Suave', hint: 'Na metade do vídeo a barra mostra ~65%' },
  { id: 'medio', label: 'Médio', hint: 'Na metade do vídeo a barra mostra 75%' },
  { id: 'forte', label: 'Forte', hint: 'Na metade do vídeo a barra mostra ~88%' },
]

export const StylingSmartProgressPanel: React.FC<StylingSmartProgressPanelProps> = ({
  smartProgress,
  onChange,
  progressBarVisible,
}) => {
  const { enabled, intensity } = smartProgress

  return (
    <div
      data-testid="styling-smart-progress-panel"
      style={{
        background: '#18181b',
        border: '1px solid #27272a',
        borderRadius: '16px',
        padding: '1.35rem',
        boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
        display: 'flex',
        flexDirection: 'column',
        gap: '1rem',
      }}
    >
      {/* Cabeçalho com Título e Switch */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <Gauge size={18} color="#f59e0b" />
          <h4 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, color: '#f4f4f5' }}>
            Progresso Inteligente
          </h4>
        </div>

        {/* Switch Toggle */}
        <button
          type="button"
          data-testid="toggle-smart-progress-switch"
          aria-pressed={enabled}
          onClick={() => onChange({ enabled: !enabled, intensity })}
          style={{
            width: '44px',
            height: '24px',
            borderRadius: '12px',
            backgroundColor: enabled ? '#3b82f6' : '#3f3f46',
            border: 'none',
            position: 'relative',
            cursor: 'pointer',
            transition: 'background-color 0.2s ease',
            padding: 0,
          }}
        >
          <span
            style={{
              width: '18px',
              height: '18px',
              borderRadius: '50%',
              backgroundColor: '#ffffff',
              position: 'absolute',
              top: '3px',
              left: enabled ? '23px' : '3px',
              transition: 'left 0.2s ease',
              boxShadow: '0 1px 3px rgba(0,0,0,0.4)',
            }}
          />
        </button>
      </div>

      {/* Descrição */}
      <p style={{ margin: 0, fontSize: '0.82rem', color: '#a1a1aa', lineHeight: 1.4 }}>
        A barra avança rápido no início e desacelera no final, fazendo o vídeo parecer mais curto.
        Com o recurso ligado, a barra fica só visual (sem arrastar nem pular capítulos).
      </p>

      {enabled && !progressBarVisible && (
        <p
          data-testid="smart-progress-hidden-warning"
          style={{ margin: 0, fontSize: '0.8rem', color: '#fbbf24', lineHeight: 1.4 }}
        >
          A "Barra de progresso" está oculta nos controles, então este recurso não terá efeito.
        </p>
      )}

      {/* Intensidade (se habilitado) */}
      {enabled && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem' }}>
            {INTENSITY_OPTIONS.map((opt) => {
              const isActive = intensity === opt.id
              return (
                <button
                  key={opt.id}
                  type="button"
                  data-testid={`smart-progress-intensity-${opt.id}`}
                  aria-pressed={isActive}
                  title={opt.hint}
                  onClick={() => onChange({ enabled, intensity: opt.id })}
                  style={{
                    padding: '0.55rem 0.5rem',
                    borderRadius: '8px',
                    border: `1px solid ${isActive ? '#3b82f6' : '#3f3f46'}`,
                    backgroundColor: isActive ? 'rgba(59, 130, 246, 0.15)' : '#27272a',
                    color: isActive ? '#bfdbfe' : '#d4d4d8',
                    fontWeight: 700,
                    fontSize: '0.85rem',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {opt.label}
                </button>
              )
            })}
          </div>
          <p style={{ margin: 0, fontSize: '0.78rem', color: '#71717a', lineHeight: 1.4 }}>
            {INTENSITY_OPTIONS.find((o) => o.id === intensity)?.hint}. Dica: oculte o "Tempo do Vídeo" para
            a contagem regressiva não contradizer a barra.
          </p>
        </div>
      )}
    </div>
  )
}
