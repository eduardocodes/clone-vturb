import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { EmbedPlayer } from '../components/EmbedPlayer'
import type { Video } from '../types/video'

const mockDirectVideo: Video = {
  id: 'vid-direct-audio-1',
  title: 'Vídeo Direto Com Som',
  video_url: 'https://cdn.exemplo.com/direct.mp4',
  duration: 120,
  player_settings: {
    smart_autoplay: {
      enabled: true,
      mode: 'direct',
    },
  },
}

describe('EmbedPlayer Direct Audio and Unlock Tests', () => {
  it('desmuta o áudio ao receber mensagem de interação do documento pai (VTURB_PARENT_INTERACTION)', async () => {
    let playCallCount = 0
    let rejectFirstPlay = true

    // Simula bloqueio de áudio autônomo pelo browser na 1ª tentativa
    window.HTMLMediaElement.prototype.play = vi.fn().mockImplementation(() => {
      playCallCount++
      if (rejectFirstPlay) {
        rejectFirstPlay = false
        return Promise.reject(new Error('NotAllowedError: play() failed because the user didn\'t interact first.'))
      }
      return Promise.resolve()
    })

    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/videos/')) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockDirectVideo),
        })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ status: 'ok' }),
      })
    })

    const { container } = render(<EmbedPlayer videoId={mockDirectVideo.id} />)

    await waitFor(() => {
      const videoEl = container.querySelector('video')
      expect(videoEl).toBeInTheDocument()
    })

    const videoEl = container.querySelector('video') as HTMLVideoElement

    // Após rejeição de áudio não interagido, o player toca mutado como fallback seguro
    // e deve exibir o banner informativo discreto com o botão para ativar áudio
    await waitFor(() => {
      expect(videoEl.muted).toBe(true)
      expect(screen.getByTestId('direct-unmute-banner')).toBeInTheDocument()
    })

    // Clica diretamente no banner para ativar o som
    const banner = screen.getByTestId('direct-unmute-banner')
    banner.click()

    await waitFor(() => {
      // Deve ter desmutado automaticamente e removido o banner da tela
      expect(videoEl.muted).toBe(false)
      expect(videoEl.volume).toBe(1.0)
      expect(screen.queryByTestId('direct-unmute-banner')).not.toBeInTheDocument()
    })
  })

  it('sincroniza o visitor_id 1st-party vindo da URL (?sid=) e bloqueia retenção/CTA durante Smart Autoplay mudo até o clique', async () => {
    const originalUrl = window.location.href
    window.history.pushState({}, '', '/embed/vid-smart-muted?sid=vis_quiz_lead_999')

    const mockSmartMutedVideo: Video = {
      id: 'vid-smart-muted',
      title: 'VSL Smart Autoplay Mudo',
      video_url: 'https://cdn.exemplo.com/smart.mp4',
      duration: 100,
      player_settings: {
        cta_time: 40,
        smart_autoplay: {
          enabled: true,
          mode: 'smart',
          button_text: 'CLIQUE PARA OUVIR',
        },
      },
    }

    window.HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined)

    const telemetryEvents: Array<{ event_type: string; session_id: string }> = []
    global.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      if (url.includes('/events') && init?.body) {
        telemetryEvents.push(JSON.parse(init.body as string))
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'ok' }) })
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockSmartMutedVideo),
      })
    })

    const { container } = render(<EmbedPlayer videoId={mockSmartMutedVideo.id} />)

    await waitFor(() => {
      expect(container.querySelector('video')).toBeInTheDocument()
    })

    const videoEl = container.querySelector('video') as HTMLVideoElement
    Object.defineProperty(videoEl, 'duration', { value: 100, writable: true })

    // Simula o vídeo rodando mudo atrás da capa aos 50s (passou de 25%, 50% e do CTA de 40s)
    videoEl.currentTime = 50
    videoEl.dispatchEvent(new Event('timeupdate'))

    // NENHUM evento de progress_25, progress_50 ou cta_reached deve ter sido enviado enquanto mudo no Smart Autoplay!
    expect(telemetryEvents.some((e) => e.event_type === 'progress_25')).toBe(false)
    expect(telemetryEvents.some((e) => e.event_type === 'progress_50')).toBe(false)
    expect(telemetryEvents.some((e) => e.event_type === 'cta_reached')).toBe(false)

    // O evento de impression deve ter usado o sid 1st-party da página mãe do Quiz
    expect(telemetryEvents.some((e) => e.event_type === 'impression' && e.session_id === 'vis_quiz_lead_999')).toBe(true)

    window.history.pushState({}, '', originalUrl)
  })
})
