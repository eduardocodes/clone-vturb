import React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MetricsOverviewSection } from '../components/video-detail/metrics/MetricsOverviewSection'
import { RetentionFunnelSection } from '../components/video-detail/metrics/RetentionFunnelSection'
import { VideoMetricsTab } from '../components/video-detail/VideoMetricsTab'
import type { Video, VideoMetrics } from '../types/video'
import * as api from '../services/api'

describe('CtaMetricsDisplay - Exibição em Destaque do Momento da Oferta (CTA)', () => {
  const mockVideo: Video = {
    id: 'vid-test-cta-100',
    title: 'Vídeo VSL Pitch',
    video_url: 'https://cdn.vturb.com/vsl.mp4',
    thumbnail_url: undefined,
    duration: 300, // 5 minutos
    player_settings: {
      primary_color: '#4f46e5',
      autoplay: false,
      show_controls: true,
      cta_enabled: false,
      cta_time: 135, // 02:15
      cta_text: 'Comprar',
      cta_link: 'https://exemplo.com',
    },
    created_at: '2026-09-20T12:00:00Z',
    updated_at: '2026-09-20T12:00:00Z',
  }

  const mockMetricsWithCta: VideoMetrics = {
    video_id: mockVideo.id,
    total_impressions: 100,
    unique_impressions: 80,
    total_plays: 50,
    unique_plays: 40,
    play_rate: 50.0,
    total_clicks: 10,
    ctr: 20.0,
    avg_watch_time_seconds: 120,
    retention: {
      '25%': 35,
      '50%': 25,
      '75%': 15,
      '100%': 5,
    },
    cta_metric: {
      cta_time_seconds: 135,
      cta_time_formatted: '02:15',
      audience_reached: 28,
      retention_percent: 70.0,
    },
  }

  it('renderiza o card de destaque de CTA com audiência e porcentagem na visão geral', () => {
    render(<MetricsOverviewSection metrics={mockMetricsWithCta} />)

    const card = screen.getByTestId('metric-cta-reached-card')
    expect(card).toBeInTheDocument()
    expect(card).toHaveTextContent('Chegaram na Oferta (CTA)')
    expect(card).toHaveTextContent('02:15')

    const audience = screen.getByTestId('metric-cta-audience')
    expect(audience).toHaveTextContent('28 pessoas')
    expect(card).toHaveTextContent('70% de retenção no pitch')
  })

  it('exibe "1 pessoa" no singular quando apenas 1 espectador único chega na CTA', () => {
    const singlePersonMetrics: VideoMetrics = {
      ...mockMetricsWithCta,
      unique_plays: 4,
      cta_metric: {
        cta_time_seconds: 240,
        cta_time_formatted: '04:00',
        audience_reached: 1,
        retention_percent: 25.0,
      },
    }
    render(<MetricsOverviewSection metrics={singlePersonMetrics} />)
    expect(screen.getByTestId('metric-cta-audience')).toHaveTextContent('1 pessoa')
    expect(screen.getByTestId('metric-cta-reached-card')).toHaveTextContent('25% de retenção no pitch')
  })

  it('renderiza o card de CTA indicando definição de horário quando não houver cta_metric', () => {
    const metricsWithoutCta: VideoMetrics = {
      ...mockMetricsWithCta,
      cta_metric: null,
    }

    render(<MetricsOverviewSection metrics={metricsWithoutCta} />)

    const card = screen.getByTestId('metric-cta-reached-card')
    expect(card).toBeInTheDocument()
    expect(card).toHaveTextContent('Definir horário')
    expect(card).toHaveTextContent('Configure o momento da oferta no painel')
  })

  it('renderiza a etapa de oferta destacada com barra no funil de retenção', () => {
    render(<RetentionFunnelSection metrics={mockMetricsWithCta} />)

    const stage = screen.getByTestId('funnel-cta-stage')
    expect(stage).toBeInTheDocument()
    expect(stage).toHaveTextContent('Chegaram na Oferta (CTA aos 02:15)')
    expect(stage).toHaveTextContent('28 views (70%)')
  })

  it('renderiza a barra de configuração rápida de CTA no VideoMetricsTab e salva novo horário', async () => {
    vi.spyOn(api, 'fetchVideoMetrics').mockResolvedValue(mockMetricsWithCta)
    const updateSpy = vi.spyOn(api, 'updateVideo').mockResolvedValue({
      ...mockVideo,
      player_settings: {
        ...mockVideo.player_settings,
        cta_time: 195, // 03:15
      },
    })
    const showToast = vi.fn()

    render(<VideoMetricsTab video={mockVideo} showToast={showToast} />)

    // Verifica card de configuração
    expect(screen.getByTestId('metrics-cta-config-card')).toBeInTheDocument()
    expect(screen.getByText('Configurar Momento da Oferta (CTA)')).toBeInTheDocument()

    const inputMin = screen.getByTestId('input-cta-minutes')
    const inputSec = screen.getByTestId('input-cta-seconds')
    const btnSave = screen.getByTestId('btn-save-cta-time')

    // Altera para 3 minutos e 15 segundos
    fireEvent.change(inputMin, { target: { value: '3' } })
    fireEvent.change(inputSec, { target: { value: '15' } })
    fireEvent.click(btnSave)

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith(mockVideo.id, {
        player_settings: expect.objectContaining({
          cta_time: 195,
        }),
      })
      expect(showToast).toHaveBeenCalledWith('Momento da oferta (CTA) salvo com sucesso!')
    })
  })
})
