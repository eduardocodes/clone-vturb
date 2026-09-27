import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import type { Video } from '../types/video'

const hlsInstances: Array<{ loadSource: ReturnType<typeof vi.fn>; attachMedia: ReturnType<typeof vi.fn> }> = []
let releaseHls!: () => void

vi.mock('hls.js/light', async () => {
  // Segura o "download" do hls.js até o teste liberar
  await new Promise<void>((resolve) => (releaseHls = resolve))
  class FakeHls {
    static isSupported = () => true
    static Events = { ERROR: 'hlsError' }
    loadSource = vi.fn()
    attachMedia = vi.fn()
    destroy = vi.fn()
    on = vi.fn()
    constructor() {
      hlsInstances.push(this)
    }
  }
  return { default: FakeHls }
})

import { EmbedPlayer } from '../components/EmbedPlayer'

const base: Video = {
  id: 'vid-hls-1',
  title: 'VSL em HLS',
  video_url: 'https://video.exemplo.com/videos/x/source.mp4',
  duration: 120,
  player_settings: { smart_autoplay: { enabled: true, mode: 'direct' } },
}

function mockApi(video: Video) {
  global.fetch = vi.fn().mockImplementation((url: string) =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve(url.includes(`/videos/${video.id}`) && !url.includes('/events') ? video : { status: 'ok' }),
    })
  )
}

describe('EmbedPlayer com HLS', () => {
  beforeEach(() => {
    hlsInstances.length = 0
    window.HTMLMediaElement.prototype.play = vi.fn().mockResolvedValue(undefined)
  })

  it('não baixa o MP4 e só dá autoplay depois que o hls.js anexa a playlist', async () => {
    const hlsUrl = 'https://video.exemplo.com/videos/x/hls/7/master.m3u8'
    mockApi({ ...base, hls_url: hlsUrl })

    const { container } = render(<EmbedPlayer videoId={base.id} />)
    await waitFor(() => expect(container.querySelector('video')).toBeInTheDocument())
    const videoEl = container.querySelector('video') as HTMLVideoElement

    expect(videoEl.getAttribute('src')).toBeNull()
    expect(window.HTMLMediaElement.prototype.play).not.toHaveBeenCalled()

    releaseHls()

    await waitFor(() => expect(hlsInstances[0]?.attachMedia).toHaveBeenCalledWith(videoEl))
    expect(hlsInstances[0].loadSource).toHaveBeenCalledWith(hlsUrl)
    await waitFor(() => expect(window.HTMLMediaElement.prototype.play).toHaveBeenCalled())
  })

  it('vídeo sem HLS continua com o MP4 no src', async () => {
    mockApi(base)
    const { container } = render(<EmbedPlayer videoId={base.id} />)
    await waitFor(() => expect(container.querySelector('video')).toBeInTheDocument())
    expect(container.querySelector('video')!.getAttribute('src')).toBe(base.video_url)
    await waitFor(() => expect(window.HTMLMediaElement.prototype.play).toHaveBeenCalled())
  })
})
