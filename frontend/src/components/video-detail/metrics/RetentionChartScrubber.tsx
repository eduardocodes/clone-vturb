import React from 'react'

interface RetentionChartScrubberProps {
  cursorPercent: number
  dotYPct: number
  activeTab: string
  selectedHourData: {
    hour: number
    label: string
    impressions: number
    plays: number
  }
  currentTimeFormatted: string
  currentRetentionData: {
    retention: number
    audience: number
  }
}

export const RetentionChartScrubber: React.FC<RetentionChartScrubberProps> = ({
  cursorPercent,
  dotYPct,
  activeTab,
  selectedHourData,
  currentTimeFormatted,
  currentRetentionData,
}) => {
  return (
    <div
      data-testid="vturb-chart-scrubber"
      style={{
        position: 'absolute',
        left: `${cursorPercent}%`,
        top: 0,
        bottom: 0,
        width: '1px',
        borderLeft: '1px dashed rgba(255, 255, 255, 0.55)',
        pointerEvents: 'none',
        zIndex: 4,
      }}
    >
      {/* Ponto Verde centralizado exatamente no meio da linha */}
      <div
        data-testid="vturb-chart-dot"
        style={{
          position: 'absolute',
          top: `${dotYPct}%`,
          left: '0px',
          width: '11px',
          height: '11px',
          borderRadius: '50%',
          background: '#22c55e',
          border: '2px solid #ffffff',
          boxShadow: '0 0 10px #22c55e',
          transform: 'translate(-50%, -50%)',
          boxSizing: 'border-box',
        }}
      />

      {/* Card de Tooltip Flutuante Estilo VTurb Oficial */}
      <div
        data-testid="vturb-chart-tooltip"
        style={{
          position: 'absolute',
          top: cursorPercent > 50 && dotYPct > 50 ? '30%' : '45%',
          left: cursorPercent > 65 ? '-185px' : '15px',
          width: '165px',
          background: 'rgba(13, 17, 23, 0.95)',
          border: '1px solid rgba(255, 255, 255, 0.12)',
          borderRadius: '8px',
          padding: '0.65rem 0.85rem',
          color: '#ffffff',
          boxShadow: '0 8px 24px rgba(0, 0, 0, 0.7)',
          backdropFilter: 'blur(8px)',
          zIndex: 10,
          pointerEvents: 'none',
        }}
      >
        <div
          data-testid="vturb-tooltip-header"
          style={{
            fontSize: '0.82rem',
            fontWeight: 700,
            marginBottom: '0.45rem',
            color: '#f8fafc',
            borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
            paddingBottom: '0.3rem',
          }}
        >
          {activeTab === 'hourly'
            ? `${selectedHourData.label} - ${(selectedHourData.hour + 1) % 24}:00`
            : `${currentTimeFormatted} - ${cursorPercent}%`}
        </div>

        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '0.75rem',
            marginBottom: '0.3rem',
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#94a3b8' }}>
            <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#22c55e' }} />
            Audiência
          </span>
          <strong data-testid="vturb-tooltip-audience" style={{ color: '#ffffff' }}>
            {activeTab === 'hourly' ? selectedHourData.plays : currentRetentionData.audience}
          </strong>
        </div>

        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            fontSize: '0.75rem',
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#94a3b8' }}>
            <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#22c55e' }} />
            {activeTab === 'hourly' ? 'Visualizações' : 'Retenção'}
          </span>
          <strong data-testid="vturb-tooltip-retention" style={{ color: '#ffffff' }}>
            {activeTab === 'hourly'
              ? selectedHourData.impressions
              : `${currentRetentionData.retention.toFixed(2).replace('.', ',')}%`}
          </strong>
        </div>
      </div>
    </div>
  )
}
