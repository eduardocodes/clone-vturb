import React from 'react'
import { Play, UserCheck, Users, Eye, Clock, MousePointerClick, TrendingUp, Target } from 'lucide-react'
import type { VideoMetrics } from '../../../types/video'

interface MetricsOverviewSectionProps {
  metrics: VideoMetrics
}

export const MetricsOverviewSection: React.FC<MetricsOverviewSectionProps> = ({ metrics }) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Grid de KPIs principais */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '1rem',
        }}
      >
        {/* Chegaram na Oferta (CTA) */}
        <div
          data-testid="metric-cta-reached-card"
          style={{
            background: metrics.cta_metric ? 'linear-gradient(135deg, #ffffff 0%, #fffbeb 100%)' : '#ffffff',
            padding: '1.25rem',
            borderRadius: '12px',
            border: metrics.cta_metric ? '1px solid #fcd34d' : '1px dashed #cbd5e1',
            boxShadow: metrics.cta_metric ? '0 2px 8px rgba(245, 158, 11, 0.15)' : '0 1px 3px rgba(0,0,0,0.04)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: '#d97706', fontSize: '0.8rem', fontWeight: 700, marginBottom: '0.5rem' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Target size={16} color="#d97706" />
              Chegaram na Oferta (CTA)
            </span>
            {metrics.cta_metric && (
              <span style={{ background: '#fef3c7', color: '#92400e', padding: '0.15rem 0.45rem', borderRadius: '4px', fontSize: '0.72rem', fontWeight: 700 }}>
                {metrics.cta_metric.cta_time_formatted}
              </span>
            )}
          </div>
          <div data-testid="metric-cta-audience" style={{ fontSize: '1.85rem', fontWeight: 800, color: metrics.cta_metric ? '#b45309' : '#94a3b8' }}>
            {metrics.cta_metric
              ? `${metrics.cta_metric.audience_reached} ${metrics.cta_metric.audience_reached === 1 ? 'pessoa' : 'pessoas'}`
              : 'Definir horário'}
          </div>
          <div style={{ fontSize: '0.75rem', color: metrics.cta_metric ? '#78350f' : '#94a3b8', marginTop: '0.25rem', fontWeight: 600 }}>
            {metrics.cta_metric
              ? `${metrics.cta_metric.retention_percent}% de retenção no pitch`
              : 'Configure o momento da oferta no painel'}
          </div>
        </div>

        {/* Plays Totais */}
        <div style={{ background: '#ffffff', padding: '1.25rem', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#64748b', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem' }}>
            <Play size={15} color="#10b981" /> Plays Totais
          </div>
          <div data-testid="metric-total-plays" style={{ fontSize: '1.85rem', fontWeight: 800, color: '#0f172a' }}>
            {metrics.total_plays}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.25rem' }}>Inícios de reprodução</div>
        </div>

        {/* Plays Únicos */}
        <div style={{ background: '#ffffff', padding: '1.25rem', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#059669', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem' }}>
            <UserCheck size={15} color="#059669" /> Plays Únicos
          </div>
          <div data-testid="metric-unique-plays" style={{ fontSize: '1.85rem', fontWeight: 800, color: '#059669' }}>
            {metrics.unique_plays ?? metrics.total_plays}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.25rem' }}>Espectadores distintos</div>
        </div>

        {/* Play Rate */}
        <div style={{ background: '#ffffff', padding: '1.25rem', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#64748b', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem' }}>
            <TrendingUp size={15} color="#4f46e5" /> Play Rate
          </div>
          <div style={{ fontSize: '1.85rem', fontWeight: 800, color: '#4f46e5' }}>
            {metrics.play_rate}%
          </div>
          <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.25rem' }}>Plays / Impressões</div>
        </div>

        {/* Impressões Únicas (Visitantes) */}
        <div style={{ background: '#ffffff', padding: '1.25rem', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#2563eb', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem' }}>
            <Users size={15} color="#2563eb" /> Visitantes Únicos
          </div>
          <div data-testid="metric-unique-impressions" style={{ fontSize: '1.85rem', fontWeight: 800, color: '#2563eb' }}>
            {metrics.unique_impressions ?? metrics.total_impressions}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.25rem' }}>Usuários diferentes</div>
        </div>

        {/* Impressões Totais */}
        <div style={{ background: '#ffffff', padding: '1.25rem', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#64748b', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem' }}>
            <Eye size={15} color="#60a5fa" /> Impressões Totais
          </div>
          <div data-testid="metric-total-impressions" style={{ fontSize: '1.85rem', fontWeight: 800, color: '#0f172a' }}>
            {metrics.total_impressions}
          </div>
          <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.25rem' }}>Carregamentos do player</div>
        </div>

        {/* Tempo Médio */}
        <div style={{ background: '#ffffff', padding: '1.25rem', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#64748b', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem' }}>
            <Clock size={15} color="#8b5cf6" /> Tempo Médio
          </div>
          <div style={{ fontSize: '1.85rem', fontWeight: 800, color: '#8b5cf6' }}>
            {metrics.avg_watch_time_seconds}s
          </div>
          <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.25rem' }}>Retenção por espectador</div>
        </div>

        {/* Cliques / CTR */}
        <div style={{ background: '#ffffff', padding: '1.25rem', borderRadius: '12px', border: '1px solid #e2e8f0', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#d97706', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem' }}>
            <MousePointerClick size={15} color="#d97706" /> Cliques / CTR
          </div>
          <div style={{ fontSize: '1.85rem', fontWeight: 800, color: '#d97706' }}>
            {metrics.total_clicks}{' '}
            <span style={{ fontSize: '0.9rem', color: '#64748b', fontWeight: 600 }}>({metrics.ctr}%)</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '0.25rem' }}>Taxa de conversão no CTA</div>
        </div>
      </div>
    </div>
  )
}
