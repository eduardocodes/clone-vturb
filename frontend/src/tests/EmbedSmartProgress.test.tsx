import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { CustomPlayerControls } from '../components/CustomPlayerControls'
import { EmbedPlayer } from '../components/EmbedPlayer'
import type { ChaptersSettings, SmartProgressSettings, Video } from '../types/video'

const chapters: ChaptersSettings = {
  enabled: true,
  items: [
    { id: 'a', time: '00:00', seconds: 0, title: 'Abertura' },
    { id: 'b', time: '00:50', seconds: 50, title: 'Pitch' },
  ],
}

function renderControls(opts: { currentTime: number; smartProgress?: SmartProgressSettings; chapters?: ChaptersSettings }) {
  const onSeek = vi.fn()
  render(
    <CustomPlayerControls
      isPlaying
      isMuted={false}
      currentTime={opts.currentTime}
      duration={100}
      currentSpeed={1}
      primaryColor="#ef4444"
      chapters={opts.chapters}
      smartProgress={opts.smartProgress}
      onTogglePlay={vi.fn()}
      onToggleMute={vi.fn()}
      onRewind10={vi.fn()}
      onForward10={vi.fn()}
      onCycleSpeed={vi.fn()}
      onToggleFullscreen={vi.fn()}
      onSeek={onSeek}
    />
  )
  return { onSeek }
}

describe('Embed - Progresso Inteligente na barra do player', () => {
  it('ligado, os controles não desenham barra (a faixa fica fora deles, no container do player)', () => {
    renderControls({ currentTime: 50, smartProgress: { enabled: true, intensity: 'medio' }, chapters })

    expect(screen.queryByTestId('embed-progress-bar')).not.toBeInTheDocument()
    expect(screen.queryByTestId('embed-smart-progress-bar')).not.toBeInTheDocument()
    expect(screen.queryByTestId('embed-chapters-progress-bar')).not.toBeInTheDocument()
    expect(screen.getByTestId('embed-control-play')).toBeInTheDocument()
  })

  it('desligado, mantém o range arrastável e os capítulos clicáveis como antes', () => {
    const { onSeek } = renderControls({ currentTime: 25, smartProgress: { enabled: false, intensity: 'forte' } })
    expect(screen.queryByTestId('embed-smart-progress-bar')).not.toBeInTheDocument()
    fireEvent.change(screen.getByTestId('embed-progress-bar'), { target: { value: '40' } })
    expect(onSeek).toHaveBeenCalledWith(40)
  })

  it('desligado com capítulos, clique no segmento continua levando ao início do capítulo', () => {
    const { onSeek } = renderControls({ currentTime: 25, chapters })
    fireEvent.click(screen.getByTestId('embed-chapter-segment-1'))
    expect(onSeek).toHaveBeenCalledWith(50)
  })

  it('EmbedPlayer renderiza a faixa fora dos controles', async () => {
    const video: Video = {
      id: 'vid-embed-smart-progress',
      title: 'Embed com Progresso Inteligente',
      video_url: 'https://cdn.exemplo.com/video.mp4',
      duration: 120,
      player_settings: {
        primary_color: '#4f46e5',
        autoplay: false,
        show_controls: true,
        cta_enabled: false,
        cta_time: 0,
        cta_text: '',
        cta_link: '',
        smart_progress: { enabled: true, intensity: 'suave' },
      },
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }
    global.fetch = vi.fn().mockImplementation((url: string) =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve(url.includes('/videos/') ? video : { status: 'ok' }),
      })
    )

    render(<EmbedPlayer videoId={video.id} />)

    await waitFor(() => {
      expect(screen.getByTestId('embed-smart-progress-strip')).toBeInTheDocument()
    })
    expect(screen.getByTestId('embed-smart-progress-bar')).toBeInTheDocument()
    expect(screen.queryByTestId('embed-progress-bar')).not.toBeInTheDocument()
    // Faixa sempre visível: não pode morar dentro dos controles, que somem com o mouse parado
    const controls = screen.queryByTestId('embed-custom-controls')
    if (controls) expect(controls).not.toContainElement(screen.getByTestId('embed-smart-progress-strip'))
  })
})
