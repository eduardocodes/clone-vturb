import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { VideoProcessingBadge } from '../components/VideoProcessingBadge'
import type { Video } from '../types/video'

const base: Video = {
  id: 'v1',
  title: 'VSL',
  video_url: 'https://video.exemplo.com/videos/x/source.mp4',
  duration: 0,
  player_settings: {},
}

describe('VideoProcessingBadge', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('vídeo pronto não mostra nada', () => {
    const { container } = render(<VideoProcessingBadge video={{ ...base, status: 'ready' }} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('vídeo processando avisa que o original segue tocando', () => {
    render(<VideoProcessingBadge video={{ ...base, status: 'processing' }} />)
    const badge = screen.getByTestId('video-processing-badge-v1')
    expect(badge).toHaveTextContent('Processando')
    expect(badge.getAttribute('title')).toMatch(/arquivo original/)
  })

  it('falha mostra o motivo e permite reprocessar', async () => {
    const onReprocess = vi.fn().mockResolvedValue(undefined)
    render(
      <VideoProcessingBadge video={{ ...base, status: 'failed', processing_error: 'Arquivo corrompido' }} onReprocess={onReprocess} />
    )
    expect(screen.getByTestId('video-processing-badge-v1')).toHaveTextContent('Falhou')
    expect(screen.getByTestId('video-processing-badge-v1').getAttribute('title')).toContain('Arquivo corrompido')

    await act(async () => {
      fireEvent.click(screen.getByTestId('video-reprocess-btn-v1'))
    })
    expect(onReprocess).toHaveBeenCalledWith(expect.objectContaining({ id: 'v1' }))
  })

  it('sem onReprocess não mostra o botão', () => {
    render(<VideoProcessingBadge video={{ ...base, status: 'failed' }} />)
    expect(screen.queryByTestId('video-reprocess-btn-v1')).toBeNull()
  })

  it('enquanto processa, consulta de novo até ficar pronto', async () => {
    const fetchVideo = vi
      .fn()
      .mockResolvedValueOnce({ ...base, status: 'processing' })
      .mockResolvedValueOnce({ ...base, status: 'ready', hls_url: 'https://h/master.m3u8' })
    const onChange = vi.fn()
    render(
      <VideoProcessingBadge video={{ ...base, status: 'processing' }} onChange={onChange} fetchVideo={fetchVideo} pollMs={10_000} />
    )

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000)
    })
    expect(onChange).not.toHaveBeenCalled()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000)
    })
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ status: 'ready' }))
    expect(fetchVideo).toHaveBeenCalledTimes(2)
  })

  it('não consulta vídeo que não está processando', async () => {
    const fetchVideo = vi.fn()
    render(<VideoProcessingBadge video={{ ...base, status: 'failed' }} onChange={vi.fn()} fetchVideo={fetchVideo} pollMs={1000} />)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000)
    })
    expect(fetchVideo).not.toHaveBeenCalled()
  })
})
