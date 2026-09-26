import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { StylingProgressBar } from '../components/video-detail/styling/StylingProgressBar'
import { VideoStylingTab } from '../components/video-detail/VideoStylingTab'
import type { ChaptersSettings, Video } from '../types/video'

const chapters: ChaptersSettings = {
  enabled: true,
  items: [
    { id: 'c1', seconds: 0, time: '00:00', title: 'Intro' },
    { id: 'c2', seconds: 50, time: '00:50', title: 'Oferta' },
  ],
}

describe('StylingProgressBar - Progresso Inteligente na prévia', () => {
  it('ligado, não desenha barra nos controles (a faixa fica no container da prévia)', () => {
    const { container } = render(
      <StylingProgressBar
        chapters={chapters}
        duration={100}
        currentTime={50}
        primaryColor="#6366f1"
        smartProgress={{ enabled: true, intensity: 'forte' }}
        onSeek={vi.fn()}
        onChapterClick={vi.fn()}
      />
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('desligado, mantém range e capítulos clicáveis', () => {
    const onChapterClick = vi.fn()
    render(
      <StylingProgressBar
        chapters={chapters}
        duration={100}
        currentTime={25}
        primaryColor="#6366f1"
        smartProgress={{ enabled: false, intensity: 'medio' }}
        onSeek={vi.fn()}
        onChapterClick={onChapterClick}
      />
    )
    fireEvent.click(screen.getByTestId('chapter-segment-1'))
    expect(onChapterClick).toHaveBeenCalledWith(50)
  })

  it('com a barra de progresso oculta, nada é renderizado mesmo com o recurso ligado', () => {
    const { container } = render(
      <StylingProgressBar
        progressBar={false}
        duration={100}
        currentTime={25}
        primaryColor="#6366f1"
        smartProgress={{ enabled: true, intensity: 'medio' }}
        onSeek={vi.fn()}
        onChapterClick={vi.fn()}
      />
    )
    expect(container).toBeEmptyDOMElement()
  })
})

describe('VideoStylingTab - painel do Progresso Inteligente', () => {
  const baseVideo: Video = {
    id: 'vid-smart-panel',
    title: 'Vídeo painel progresso inteligente',
    video_url: 'https://exemplo.com/v.mp4',
    duration: 100,
    player_settings: {
      primary_color: '#6366f1',
      autoplay: false,
      show_controls: true,
      cta_enabled: false,
      cta_time: 0,
      cta_text: '',
      cta_link: '',
    },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }

  it('começa desligado; o switch mostra as intensidades e troca a prévia para a barra inteligente', () => {
    render(<VideoStylingTab video={baseVideo} onSave={vi.fn()} showToast={vi.fn()} />)

    expect(screen.getByTestId('styling-smart-progress-panel')).toBeInTheDocument()
    expect(screen.queryByTestId('smart-progress-intensity-medio')).not.toBeInTheDocument()
    expect(screen.getByTestId('styling-progress-bar')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('toggle-smart-progress-switch'))

    expect(screen.getByTestId('smart-progress-intensity-suave')).toBeInTheDocument()
    expect(screen.getByTestId('smart-progress-intensity-medio')).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByTestId('smart-progress-intensity-forte')).toBeInTheDocument()
    expect(screen.getByTestId('smart-progress-bar')).toBeInTheDocument()
    expect(screen.queryByTestId('styling-progress-bar')).not.toBeInTheDocument()
    expect(screen.getByTestId('styling-video-preview-container')).toContainElement(
      screen.getByTestId('styling-smart-progress-strip')
    )
    expect(screen.getByTestId('styling-player-controls-bar')).not.toContainElement(
      screen.getByTestId('smart-progress-bar')
    )

    fireEvent.click(screen.getByTestId('toggle-smart-progress-switch'))
    expect(screen.queryByTestId('smart-progress-intensity-medio')).not.toBeInTheDocument()
    expect(screen.getByTestId('styling-progress-bar')).toBeInTheDocument()
  })

  it('avisa quando a barra de progresso está oculta', () => {
    render(
      <VideoStylingTab
        video={{
          ...baseVideo,
          player_settings: {
            ...baseVideo.player_settings,
            controls_config: { progress_bar: false },
            smart_progress: { enabled: true, intensity: 'medio' },
          },
        }}
        onSave={vi.fn()}
        showToast={vi.fn()}
      />
    )
    expect(screen.getByTestId('smart-progress-hidden-warning')).toBeInTheDocument()
  })

  it('salva smart_progress com a intensidade escolhida', async () => {
    const fetchMock = vi.fn().mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(baseVideo) })
    )
    global.fetch = fetchMock
    render(<VideoStylingTab video={baseVideo} onSave={vi.fn()} showToast={vi.fn()} />)

    fireEvent.click(screen.getByTestId('toggle-smart-progress-switch'))
    fireEvent.click(screen.getByTestId('smart-progress-intensity-forte'))
    expect(screen.getByTestId('smart-progress-intensity-forte')).toHaveAttribute('aria-pressed', 'true')

    await act(async () => {
      fireEvent.click(screen.getByTestId('save-styling-bottom-btn'))
    })
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())

    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(body.player_settings.smart_progress).toEqual({ enabled: true, intensity: 'forte' })
  })
})
