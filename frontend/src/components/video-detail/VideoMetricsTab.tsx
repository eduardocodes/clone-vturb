import React, { useEffect, useState, useCallback } from 'react'
import { BarChart3, Clock, Filter, RotateCcw, Target, Check } from 'lucide-react'
import type { Video, VideoMetrics } from '../../types/video'
import { fetchVideoMetrics, updateVideo } from '../../services/api'
import {
  DateFilterBar,
  MetricsOverviewSection,
  HourlyPeakSection,
  RetentionFunnelSection,
  VTurbRetentionChart,
} from './metrics'

interface VideoMetricsTabProps {
  video: Video
  showToast: (msg: string) => void
}

type MetricsSubTab = 'overview' | 'hourly' | 'retention'

export const VideoMetricsTab: React.FC<VideoMetricsTabProps> = ({ video, showToast }) => {
  const [activeSubTab, setActiveSubTab] = useState<MetricsSubTab>('overview')
  const [metrics, setMetrics] = useState<VideoMetrics | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Filtros de Data
  const [period, setPeriod] = useState<string>('all')
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')

  // Configuração rápida do Momento da Oferta (CTA)
  const currentCtaSec =
    metrics?.cta_metric?.cta_time_seconds ||
    video.player_settings?.cta_time ||
    video.player_settings?.pitch_delay?.time ||
    0
  const [ctaMinutes, setCtaMinutes] = useState<number>(Math.floor(currentCtaSec / 60))
  const [ctaSeconds, setCtaSeconds] = useState<number>(currentCtaSec % 60)
  const [savingCta, setSavingCta] = useState(false)

  useEffect(() => {
    if (currentCtaSec > 0) {
      setCtaMinutes(Math.floor(currentCtaSec / 60))
      setCtaSeconds(currentCtaSec % 60)
    }
  }, [currentCtaSec])

  const loadMetrics = useCallback(async (currentPeriod = period, start = startDate, end = endDate) => {
    try {
      setLoading(true)
      setError(null)
      const data = await fetchVideoMetrics(video.id, {
        period: currentPeriod,
        start_date: currentPeriod === 'custom' ? start : undefined,
        end_date: currentPeriod === 'custom' ? end : undefined,
      })
      setMetrics(data)
    } catch (err: any) {
      setError(err.message || 'Erro ao carregar métricas.')
      showToast('Erro ao carregar métricas do vídeo.')
    } finally {
      setLoading(false)
    }
  }, [video.id, period, startDate, endDate, showToast])

  useEffect(() => {
    if (period !== 'custom') {
      loadMetrics(period)
    }
  }, [period, loadMetrics])

  const handleApplyCustomDates = () => {
    if (!startDate && !endDate) {
      showToast('Selecione pelo menos uma data para o filtro.')
      return
    }
    loadMetrics('custom', startDate, endDate)
  }

  const handleSaveCtaTime = async () => {
    const totalSec = Math.max(0, Number(ctaMinutes) * 60 + Number(ctaSeconds))
    try {
      setSavingCta(true)
      const updatedSettings = {
        ...video.player_settings,
        cta_time: totalSec,
      }
      await updateVideo(video.id, { player_settings: updatedSettings })
      showToast('Momento da oferta (CTA) salvo com sucesso!')
      loadMetrics()
    } catch {
      showToast('Erro ao salvar momento da oferta.')
    } finally {
      setSavingCta(false)
    }
  }

  const subTabs = [
    { id: 'overview' as const, label: 'Visão Geral', icon: BarChart3, testId: 'metrics-subtab-overview' },
    { id: 'hourly' as const, label: 'Horários de Pico (24h)', icon: Clock, testId: 'metrics-subtab-hourly' },
    { id: 'retention' as const, label: 'Funil & Retenção', icon: Filter, testId: 'metrics-subtab-retention' },
  ]

  return (
    <div style={{ maxWidth: '960px', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Cabeçalho da Aba de Métricas */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h3 style={{ margin: '0 0 0.25rem', fontSize: '1.2rem', fontWeight: 700, color: '#1e293b', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <BarChart3 size={20} color="#4f46e5" />
            Performance e Telemetria
          </h3>
          <span style={{ fontSize: '0.875rem', color: '#64748b' }}>
            Dados analíticos em tempo real coletados pelo player em suas páginas de vendas.
          </span>
        </div>

        <button
          type="button"
          onClick={() => loadMetrics()}
          disabled={loading}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.4rem',
            padding: '0.5rem 1rem',
            borderRadius: '8px',
            border: '1px solid #cbd5e1',
            background: '#ffffff',
            color: '#334155',
            fontSize: '0.85rem',
            fontWeight: 600,
            cursor: loading ? 'not-allowed' : 'pointer',
            boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
          }}
        >
          <RotateCcw size={15} className={loading ? 'spin' : ''} />
          <span>{loading ? 'Atualizando...' : 'Recarregar'}</span>
        </button>
      </div>

      {/* Barra de Configuração Rápida do Momento da Oferta / CTA */}
      <div
        data-testid="metrics-cta-config-card"
        style={{
          background: '#ffffff',
          borderRadius: '12px',
          border: '1px solid #fcd34d',
          padding: '1.15rem 1.4rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
          boxShadow: '0 1px 3px rgba(245, 158, 11, 0.08)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
          <div
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '10px',
              background: '#fef3c7',
              color: '#d97706',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <Target size={22} />
          </div>
          <div>
            <h4 style={{ margin: '0 0 0.15rem', fontSize: '0.98rem', fontWeight: 700, color: '#1e293b' }}>
              Configurar Momento da Oferta (CTA)
            </h4>
            <span style={{ fontSize: '0.82rem', color: '#64748b' }}>
              Defina o minuto e segundo em que sua oferta começa para ver quantos espectadores chegam nela.
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', background: '#f8fafc', padding: '0.4rem 0.65rem', borderRadius: '8px', border: '1px solid #cbd5e1' }}>
            <input
              type="number"
              min="0"
              max="180"
              data-testid="input-cta-minutes"
              value={ctaMinutes}
              onChange={(e) => setCtaMinutes(Math.max(0, parseInt(e.target.value) || 0))}
              style={{ width: '42px', border: 'none', background: 'transparent', textAlign: 'center', fontWeight: 700, fontSize: '0.95rem', outline: 'none' }}
            />
            <span style={{ fontSize: '0.82rem', color: '#64748b', fontWeight: 600 }}>min</span>
            <span style={{ color: '#94a3b8', fontWeight: 800 }}>:</span>
            <input
              type="number"
              min="0"
              max="59"
              data-testid="input-cta-seconds"
              value={ctaSeconds}
              onChange={(e) => setCtaSeconds(Math.max(0, Math.min(59, parseInt(e.target.value) || 0)))}
              style={{ width: '42px', border: 'none', background: 'transparent', textAlign: 'center', fontWeight: 700, fontSize: '0.95rem', outline: 'none' }}
            />
            <span style={{ fontSize: '0.82rem', color: '#64748b', fontWeight: 600 }}>seg</span>
          </div>

          <button
            type="button"
            data-testid="btn-save-cta-time"
            onClick={handleSaveCtaTime}
            disabled={savingCta}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.6rem 1.15rem',
              borderRadius: '8px',
              border: 'none',
              background: '#d97706',
              color: '#ffffff',
              fontSize: '0.88rem',
              fontWeight: 700,
              cursor: savingCta ? 'not-allowed' : 'pointer',
              boxShadow: '0 2px 6px rgba(217, 119, 6, 0.25)',
            }}
          >
            <Check size={16} />
            <span>{savingCta ? 'Salvando...' : 'Salvar Momento'}</span>
          </button>
        </div>
      </div>

      {/* Barra de Filtros por Período / Data */}
      <DateFilterBar
        period={period}
        setPeriod={setPeriod}
        startDate={startDate}
        setStartDate={setStartDate}
        endDate={endDate}
        setEndDate={setEndDate}
        onApplyCustom={handleApplyCustomDates}
        loading={loading}
      />

      {/* Barra de Sub-Abas de Métricas */}
      <div
        style={{
          display: 'flex',
          gap: '0.5rem',
          background: '#f1f5f9',
          padding: '0.35rem',
          borderRadius: '10px',
          border: '1px solid #e2e8f0',
        }}
      >
        {subTabs.map((tab) => {
          const Icon = tab.icon
          const isActive = activeSubTab === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              data-testid={tab.testId}
              onClick={() => setActiveSubTab(tab.id)}
              style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem',
                padding: '0.65rem 1rem',
                borderRadius: '8px',
                border: 'none',
                background: isActive ? '#ffffff' : 'transparent',
                color: isActive ? '#4f46e5' : '#64748b',
                fontWeight: isActive ? 700 : 500,
                fontSize: '0.88rem',
                cursor: 'pointer',
                boxShadow: isActive ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
                transition: 'all 0.15s ease',
              }}
            >
              <Icon size={16} color={isActive ? '#4f46e5' : '#64748b'} />
              <span>{tab.label}</span>
            </button>
          )
        })}
      </div>

      {error && (
        <div style={{ padding: '0.85rem', background: '#fee2e2', border: '1px solid #fca5a5', borderRadius: '8px', color: '#b91c1c', fontSize: '0.9rem' }}>
          {error}
        </div>
      )}

      {loading && !metrics ? (
        <div style={{ padding: '3rem', textAlign: 'center', color: '#64748b', fontSize: '0.95rem' }}>
          Carregando indicadores analíticos...
        </div>
      ) : metrics ? (
        <>
          {/* Sub-Aba 1: Visão Geral */}
          <div style={{ display: activeSubTab === 'overview' ? 'block' : 'none' }}>
            <div style={{ marginBottom: '1.5rem' }}>
              <VTurbRetentionChart video={video} metrics={metrics} defaultTab="retention" />
            </div>
            <MetricsOverviewSection metrics={metrics} />
          </div>

          {/* Sub-Aba 2: Horários & Pico (Gráfico VTurb) */}
          <div style={{ display: activeSubTab === 'hourly' ? 'block' : 'none' }}>
            <div style={{ marginBottom: '1.5rem' }}>
              <VTurbRetentionChart video={video} metrics={metrics} defaultTab="hourly" />
            </div>
            <HourlyPeakSection metrics={metrics} />
          </div>

          {/* Sub-Aba 3: Funil & Retenção */}
          <div style={{ display: activeSubTab === 'retention' ? 'block' : 'none' }}>
            <div style={{ marginBottom: '1.5rem' }}>
              <VTurbRetentionChart video={video} metrics={metrics} defaultTab="retention" />
            </div>
            <RetentionFunnelSection metrics={metrics} />
          </div>
        </>
      ) : null}
    </div>
  )
}
