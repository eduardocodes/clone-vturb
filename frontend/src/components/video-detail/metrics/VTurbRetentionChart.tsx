import React, { useState, useRef } from 'react'
import type { Video, VideoMetrics } from '../../../types/video'
import { VTurbMetricsBreakdown, type BreakdownTab } from './VTurbMetricsBreakdown'
import { RetentionChartNavbar, type ChartTab } from './RetentionChartNavbar'
import { RetentionChartCanvas } from './RetentionChartCanvas'
import { RetentionChartScrubber } from './RetentionChartScrubber'
import {
  formatTime,
  getTimeTicks,
  hourlyTicks,
  getRetentionValues,
  getInterpolatedRetention,
  generateRetentionPaths,
  generateHourlyPaths,
  curveRetentionAt,
  generateCurvePaths,
} from './retentionChartHelpers'

interface VTurbRetentionChartProps {
  video: Video
  metrics: VideoMetrics
  defaultTab?: 'retention' | 'hourly' | BreakdownTab
}

export const VTurbRetentionChart: React.FC<VTurbRetentionChartProps> = ({
  video,
  metrics,
  defaultTab = 'retention',
}) => {
  const [activeTab, setActiveTab] = useState<ChartTab>(defaultTab)
  const [showConversions, setShowConversions] = useState(false)
  const [cursorPercent, setCursorPercent] = useState<number>(44) // Ponto padrão 44% (~01:05)
  const chartRef = useRef<HTMLDivElement>(null)

  const curveData = metrics.retention_curve && metrics.retention_curve.sessions > 0 ? metrics.retention_curve : null
  // Sem duração cadastrada, a curva indica até onde há dado; 147s é o padrão antigo do gráfico
  const duration =
    video.duration > 0
      ? video.duration
      : curveData
      ? curveData.values.length * curveData.bucket_seconds
      : 147
  const totalPlays = metrics.total_plays || 0
  const hourlyList = metrics.hourly_distribution || []

  // Marcadores de tempo do eixo X
  const timeTicks = getTimeTicks(duration)

  // Cálculo de retenção nos marcos e interpolação
  const retentionValues = getRetentionValues(metrics, totalPlays)
  const uniquePlaysCount = metrics.unique_plays ?? 0
  const audienceBase = uniquePlaysCount > 0 ? uniquePlaysCount : totalPlays

  // Dados para o modo horário (24h)
  const maxActivity = Math.max(
    ...hourlyList.map((h) => Math.max(h.impressions, h.plays)),
    1
  )
  const selectedHourIndex = Math.min(23, Math.floor((cursorPercent / 100) * 24))
  const selectedHourData = hourlyList[selectedHourIndex] || {
    hour: selectedHourIndex,
    label: `${String(selectedHourIndex).padStart(2, '0')}:00`,
    impressions: 0,
    plays: 0,
  }

  // Curva por segundo (trechos realmente assistidos) quando o backend já tem sessões;
  // sem ela (dados antigos), interpola entre os marcos de 25/50/75/100%.
  const curve = curveData
  const currentRetentionData = curve
    ? (() => {
        const retention = curveRetentionAt(curve, cursorPercent, duration)
        return { retention, audience: Math.round((retention / 100) * curve.sessions) }
      })()
    : getInterpolatedRetention(cursorPercent, retentionValues, totalPlays, audienceBase)
  const currentSecs = Math.round((cursorPercent / 100) * duration)
  const currentTimeFormatted = formatTime(currentSecs)

  // Geração dos caminhos SVG
  const { retentionPathD, retentionAreaD } = curve ? generateCurvePaths(curve, duration) : generateRetentionPaths(retentionValues)
  const { hourlyPathD, hourlyAreaD } = generateHourlyPaths(hourlyList, maxActivity)

  const activePathD = activeTab === 'hourly' ? hourlyPathD : retentionPathD
  const activeAreaD = activeTab === 'hourly' ? hourlyAreaD : retentionAreaD

  // Posição vertical do ponto no scrubber
  const dotYPct =
    activeTab === 'hourly'
      ? 100 - (selectedHourData.plays / maxActivity) * 100
      : totalPlays > 0 || curve
      ? 100 - currentRetentionData.retention
      : 98

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!chartRef.current) return
    const rect = chartRef.current.getBoundingClientRect()
    const x = e.clientX - rect.left
    const pct = Math.max(0, Math.min(100, Math.round((x / rect.width) * 100)))
    setCursorPercent(pct)
  }

  const tabs: { id: ChartTab; label: string }[] = [
    { id: 'retention', label: 'Retenção Geral' },
    { id: 'hourly', label: 'Melhores Horários (24h)' },
    { id: 'countries', label: 'Países' },
    { id: 'devices', label: 'Dispositivos' },
    { id: 'os', label: 'Sistema Operacional' },
    { id: 'browsers', label: 'Navegadores' },
    { id: 'traffic', label: 'Origem do Tráfego' },
  ]

  const isGraphView = activeTab === 'retention' || activeTab === 'hourly'

  return (
    <div
      data-testid="vturb-retention-chart"
      style={{
        background: '#0a0c10',
        borderRadius: '16px',
        padding: '1.25rem 1.5rem',
        color: '#ffffff',
        border: '1px solid #1e293b',
        boxShadow: '0 10px 30px rgba(0, 0, 0, 0.4)',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.25rem',
        fontFamily: 'system-ui, -apple-system, sans-serif',
      }}
    >
      {/* Barra de Navegação de Métricas no Topo */}
      <RetentionChartNavbar
        tabs={tabs}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        showConversions={showConversions}
        onToggleConversions={() => setShowConversions(!showConversions)}
      />

      {/* Gráfico Estilo Imagem 01 com Vídeo Centralizado */}
      {isGraphView ? (
        <div>
          <div
            style={{
              display: 'flex',
              position: 'relative',
              height: '260px',
              userSelect: 'none',
            }}
          >
            {/* Eixo Y com Porcentagens */}
            <div
              style={{
                width: '45px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                paddingRight: '0.5rem',
                fontSize: '0.72rem',
                color: '#64748b',
                fontWeight: 600,
                textAlign: 'right',
                marginBottom: '15px',
              }}
            >
              <span>100%</span>
              <span>80%</span>
              <span>60%</span>
              <span>40%</span>
              <span>20%</span>
              <span>0%</span>
            </div>

            {/* Área Principal do Gráfico (Canvas SVG + Vídeo) */}
            <RetentionChartCanvas
              chartRef={chartRef}
              onMouseMove={handleMouseMove}
              video={video}
              activeAreaD={activeAreaD}
              activePathD={activePathD}
              showConversions={showConversions}
              ctrPercent={metrics.ctr}
            >
              {/* Scrubber Interativo: Linha Vertical Tracejada e Ponto */}
              <RetentionChartScrubber
                cursorPercent={cursorPercent}
                dotYPct={dotYPct}
                activeTab={activeTab}
                selectedHourData={selectedHourData}
                currentTimeFormatted={currentTimeFormatted}
                currentRetentionData={currentRetentionData}
              />
            </RetentionChartCanvas>
          </div>

          {/* Eixo X com Timestamps ou Horários */}
          <div
            data-testid="vturb-chart-x-axis"
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              paddingLeft: '45px',
              paddingTop: '0.5rem',
              fontSize: '0.75rem',
              color: '#64748b',
              fontWeight: 600,
            }}
          >
            {(activeTab === 'hourly' ? hourlyTicks : timeTicks).map((tick, idx) => (
              <span key={idx}>{tick}</span>
            ))}
          </div>
        </div>
      ) : (
        <VTurbMetricsBreakdown tab={activeTab as BreakdownTab} />
      )}
    </div>
  )
}
