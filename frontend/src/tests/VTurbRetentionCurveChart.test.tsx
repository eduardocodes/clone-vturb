import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { VTurbRetentionChart } from '../components/video-detail/metrics/VTurbRetentionChart'
import type { Video, VideoMetrics } from '../types/video'

const video = { id: 'v1', title: 'VSL', video_url: 'x', duration: 100, player_settings: {}, created_at: '', updated_at: '' } as unknown as Video

const base: VideoMetrics = {
  video_id: 'v1',
  period: 'all',
  total_impressions: 10,
  unique_impressions: 10,
  total_plays: 10,
  unique_plays: 10,
  play_rate: 100,
  total_clicks: 0,
  ctr: 0,
  avg_watch_time_seconds: 30,
  retention: { '25%': 9, '50%': 6, '75%': 4, '100%': 2 },
  hourly_distribution: [],
}

describe('gráfico de retenção com a curva por segundo', () => {
  it('desenha a curva real (segmentos retos) quando o backend manda retention_curve', () => {
    const metrics = { ...base, retention_curve: { bucket_seconds: 1, sessions: 10, values: [1, 0.9, 0.8, 0.5, 0.5] } }
    render(<VTurbRetentionChart video={video} metrics={metrics} />)
    const d = screen.getByTestId('vturb-neon-retention-curve').getAttribute('d') || ''
    expect(d.startsWith('M 0,')).toBe(true)
    expect(d).not.toContain(' C ')
    // 5 pontos no tempo do vídeo (100 s) + queda a zero + chão até o fim
    expect(d.split(' L ').length).toBe(7)
  })

  it('sem curva (dados antigos), usa os marcos de 25/50/75/100%', () => {
    render(<VTurbRetentionChart video={video} metrics={base} />)
    expect(screen.getByTestId('vturb-neon-retention-curve').getAttribute('d')).toContain(' C ')
  })
})
