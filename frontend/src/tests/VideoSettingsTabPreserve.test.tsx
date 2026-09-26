import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { VideoSettingsTab } from '../components/video-detail/VideoSettingsTab'
import type { Video } from '../types/video'

const mockVideo: Video = {
  id: 'vid-preserve-1',
  title: 'Vídeo com configurações avançadas',
  video_url: 'https://exemplo.com/vsl.mp4',
  thumbnail_url: 'https://exemplo.com/capa.jpg',
  duration: 120,
  player_settings: {
    primary_color: '#6366f1',
    autoplay: true,
    show_controls: true,
    cta_enabled: false,
    cta_time: 30,
    cta_text: 'Comprar Agora',
    cta_link: 'https://checkout.com',
    play_button_shape: 'circle',
    play_button_size: 'medium',
    turbo_enabled: true,
    playback_rate: 1.25,
    controls_config: { progress_bar: true, video_time: false },
    chapters: { enabled: true, items: [{ id: 'c1', time: '00:00', seconds: 0, title: 'Início' }] },
    smart_progress: { enabled: true, intensity: 'forte' },
  },
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

describe('VideoSettingsTab - preservação das demais configurações do player', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('ao salvar, mantém no payload as configurações de outras abas (turbo, controles, capítulos, progresso inteligente)', async () => {
    const fetchMock = vi.fn().mockImplementation(() =>
      Promise.resolve({ ok: true, json: () => Promise.resolve(mockVideo) })
    )
    global.fetch = fetchMock

    render(<VideoSettingsTab video={mockVideo} onSave={vi.fn()} showToast={vi.fn()} />)

    await act(async () => {
      fireEvent.click(screen.getByTestId('settings-save-btn'))
    })

    await waitFor(() => expect(fetchMock).toHaveBeenCalled())

    const [, init] = fetchMock.mock.calls[0]
    const body = JSON.parse(init.body)
    expect(body.player_settings).toEqual(
      expect.objectContaining({
        turbo_enabled: true,
        playback_rate: 1.25,
        controls_config: { progress_bar: true, video_time: false },
        chapters: mockVideo.player_settings.chapters,
        smart_progress: { enabled: true, intensity: 'forte' },
        primary_color: '#6366f1',
      })
    )
  })
})
