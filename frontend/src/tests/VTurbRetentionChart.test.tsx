import React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { VTurbRetentionChart } from '../components/video-detail/metrics/VTurbRetentionChart'
import type { Video, VideoMetrics } from '../types/video'

describe('VTurbRetentionChart - Gráfico Oficial VTurb com Vídeo Centralizado', () => {
  const mockVideo: Video = {
    id: 'vid-vturb-chart-123',
    title: 'video03.mp4',
    video_url: 'https://cdn.vturb.com/videos/video03.mp4',
    thumbnail_url: 'https://s3.us-east-005.backblazeb2.com/vturb-bucket/thumbnails/video03.jpg',
    duration: 147, // 02:27
    player_settings: {
      primary_color: '#4f46e5',
      autoplay: false,
      show_controls: true,
      cta_enabled: false,
      cta_time: 0,
      cta_text: 'Comprar Agora',
      cta_link: 'https://exemplo.com',
    },
    created_at: '2026-09-15T12:00:00Z',
    updated_at: '2026-09-15T12:00:00Z',
  }

  const mockHourlyList = Array.from({ length: 24 }, (_, i) => ({
    hour: i,
    label: `${String(i).padStart(2, '0')}:00`,
    impressions: i === 19 ? 50 : 10,
    plays: i === 19 ? 35 : 5,
    clicks: 2,
  }))

  const mockMetrics: VideoMetrics = {
    video_id: mockVideo.id,
    period: 'all',
    total_impressions: 250,
    unique_impressions: 180,
    total_plays: 120,
    unique_plays: 95,
    play_rate: 48.0,
    total_clicks: 25,
    ctr: 20.8,
    avg_watch_time_seconds: 45,
    retention: { '25%': 90, '50%': 60, '75%': 40, '100%': 20 },
    hourly_distribution: mockHourlyList,
    peak_hour: {
      hour: 19,
      label: '19:00 - 20:00',
      impressions: 50,
      plays: 35,
      total_activity: 85,
    },
  }

  it('renderiza o container do gráfico, abas de navegação e imagem central do vídeo', () => {
    render(<VTurbRetentionChart video={mockVideo} metrics={mockMetrics} />)

    // 1. Container do gráfico
    expect(screen.getByTestId('vturb-retention-chart')).toBeInTheDocument()

    // 2. Abas de navegação
    expect(screen.getByTestId('vturb-tab-retention')).toBeInTheDocument()
    expect(screen.getByTestId('vturb-tab-hourly')).toBeInTheDocument()
    expect(screen.getByTestId('vturb-tab-devices')).toBeInTheDocument()
    expect(screen.getByTestId('vturb-tab-countries')).toBeInTheDocument()
    expect(screen.getByTestId('vturb-toggle-conversions')).toBeInTheDocument()

    // 3. Imagem do vídeo centralizada no gráfico
    const thumbnailWrapper = screen.getByTestId('vturb-chart-video-thumbnail')
    expect(thumbnailWrapper).toBeInTheDocument()
    const img = thumbnailWrapper.querySelector('img')
    expect(img).toBeInTheDocument()
    expect(img?.src).toContain('thumbnails/video03.jpg')
  })

  it('renderiza os eixos Y (0-100%), X (baseado na duração do vídeo) e curva neon verde', () => {
    render(<VTurbRetentionChart video={mockVideo} metrics={mockMetrics} />)

    // 1. Eixo Y com porcentagens
    expect(screen.getByText('100%')).toBeInTheDocument()
    expect(screen.getByText('80%')).toBeInTheDocument()
    expect(screen.getByText('0%')).toBeInTheDocument()

    // 2. Eixo X com marcas de tempo da duração do vídeo (147s -> 02:27)
    const xAxis = screen.getByTestId('vturb-chart-x-axis')
    expect(xAxis).toHaveTextContent('00:00')
    expect(xAxis).toHaveTextContent('02:27')

    // 3. Curva SVG neon verde
    expect(screen.getByTestId('vturb-neon-retention-curve')).toBeInTheDocument()
  })

  it('renderiza scrubber vertical tracejado com ponto verde e tooltip detalhado com audiência e retenção', () => {
    render(<VTurbRetentionChart video={mockVideo} metrics={mockMetrics} />)

    // 1. Scrubber tracejado e ponto verde
    expect(screen.getByTestId('vturb-chart-scrubber')).toBeInTheDocument()
    expect(screen.getByTestId('vturb-chart-dot')).toBeInTheDocument()

    // 2. Tooltip flutuante com dados interpolados
    const tooltip = screen.getByTestId('vturb-chart-tooltip')
    expect(tooltip).toBeInTheDocument()
    expect(screen.getByTestId('vturb-tooltip-header')).toBeInTheDocument()
    expect(screen.getByTestId('vturb-tooltip-audience')).toBeInTheDocument()
    expect(screen.getByTestId('vturb-tooltip-retention')).toBeInTheDocument()
  })

  it('atualiza posição do scrubber e dados do tooltip ao mover o mouse pelo canvas', () => {
    render(<VTurbRetentionChart video={mockVideo} metrics={mockMetrics} />)

    const canvas = screen.getByTestId('vturb-chart-canvas')
    
    // Simula getBoundingClientRect
    vi.spyOn(canvas, 'getBoundingClientRect').mockReturnValue({
      width: 500,
      height: 260,
      left: 0,
      top: 0,
      right: 500,
      bottom: 260,
      x: 0,
      y: 0,
      toJSON: () => {},
    })

    // Move mouse para 50% do canvas (x = 250)
    fireEvent.mouseMove(canvas, { clientX: 250 })

    const header = screen.getByTestId('vturb-tooltip-header')
    expect(header).toHaveTextContent('50%')
  })

  it('permite alternar para a aba de Melhores Horários (24h) e exibe horários no eixo X', () => {
    render(<VTurbRetentionChart video={mockVideo} metrics={mockMetrics} />)

    const hourlyTab = screen.getByTestId('vturb-tab-hourly')
    fireEvent.click(hourlyTab)

    // Eixo X deve mostrar horários do dia
    const xAxis = screen.getByTestId('vturb-chart-x-axis')
    expect(xAxis).toHaveTextContent('00:00')
    expect(xAxis).toHaveTextContent('12:00')
    expect(xAxis).toHaveTextContent('23:00')

    // Vídeo centralizado permanece visível
    expect(screen.getByTestId('vturb-chart-video-thumbnail')).toBeInTheDocument()
  })

  it('permite alternar para aba Dispositivos e exibe painel detalhado de breakdown', () => {
    render(<VTurbRetentionChart video={mockVideo} metrics={mockMetrics} />)

    const devicesTab = screen.getByTestId('vturb-tab-devices')
    fireEvent.click(devicesTab)

    expect(screen.getByTestId('vturb-panel-devices')).toBeInTheDocument()
    // Sem coleta de dispositivo no player: o painel avisa em vez de mostrar números de exemplo
    expect(screen.getByTestId('vturb-panel-devices-empty')).toHaveTextContent(/ainda não coletamos/i)
    expect(screen.queryByText(/82%/)).not.toBeInTheDocument()
  })

  it('trata graciosamente vídeo sem thumbnail exibindo fallback elegante', () => {
    const videoSemThumb: Video = {
      ...mockVideo,
      thumbnail_url: undefined,
    }

    render(<VTurbRetentionChart video={videoSemThumb} metrics={mockMetrics} />)

    const thumbnailWrapper = screen.getByTestId('vturb-chart-video-thumbnail')
    expect(thumbnailWrapper).toBeInTheDocument()
    expect(thumbnailWrapper.querySelector('img')).toBeNull()
    expect(thumbnailWrapper).toHaveTextContent('video03.mp4')
  })
})
