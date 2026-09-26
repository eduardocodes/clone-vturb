import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'

const uploadMedia = vi.fn()
const createVideo = vi.fn()

vi.mock('../services/directUpload', () => ({
  uploadMedia: (...args: unknown[]) => uploadMedia(...args),
}))
vi.mock('../services/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../services/api')>()
  return { ...original, createVideo: (...args: unknown[]) => createVideo(...args) }
})

import { VideoCreateView } from '../components/video-create/VideoCreateView'

const KEY = 'videos/11111111-1111-1111-1111-111111111111/source.mp4'
const URL_PUBLICA = `https://video.exemplo.com/${KEY}`

function renderView() {
  render(<VideoCreateView onBack={() => {}} onSuccess={() => {}} showToast={() => {}} />)
}

async function uploadVideo() {
  const file = new File([new Uint8Array(10)], 'vsl.mp4', { type: 'video/mp4' })
  await act(async () => {
    fireEvent.change(screen.getByTestId('create-video-file-input'), { target: { files: [file] } })
  })
  await waitFor(() => expect(uploadMedia).toHaveBeenCalled())
}

describe('VideoCreateView com upload direto para o storage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    uploadMedia.mockImplementation(async (_file: File, _kind: string, opts?: { onProgress?: (p: number) => void }) => {
      opts?.onProgress?.(50)
      opts?.onProgress?.(100)
      return { url: URL_PUBLICA, storageKey: KEY, sizeBytes: 10 }
    })
    createVideo.mockResolvedValue({ id: 'v1', title: 'Vsl', video_url: URL_PUBLICA, duration: 0, player_settings: {}, created_at: '', updated_at: '' })
  })

  it('envia o vídeo direto e cria o vídeo com a chave do storage', async () => {
    renderView()
    await uploadVideo()

    expect(uploadMedia).toHaveBeenCalledWith(expect.any(File), 'video', expect.objectContaining({ onProgress: expect.any(Function) }))

    await act(async () => {
      fireEvent.click(screen.getByTestId('create-video-submit-btn'))
    })

    await waitFor(() => expect(createVideo).toHaveBeenCalled())
    expect(createVideo.mock.calls[0][0]).toMatchObject({
      video_url: URL_PUBLICA,
      storage_key: KEY,
      source_size_bytes: 10,
    })
  })

  it('se o usuário troca para URL externa, não manda a chave antiga', async () => {
    renderView()
    await uploadVideo()

    fireEvent.click(screen.getByTestId('create-video-mode-url'))
    fireEvent.change(screen.getByTestId('create-video-url-input'), {
      target: { value: 'https://cdn.externa.com/outra.mp4' },
    })
    await act(async () => {
      fireEvent.click(screen.getByTestId('create-video-submit-btn'))
    })

    await waitFor(() => expect(createVideo).toHaveBeenCalled())
    const body = createVideo.mock.calls[0][0]
    expect(body.video_url).toBe('https://cdn.externa.com/outra.mp4')
    expect(body).not.toHaveProperty('storage_key')
  })
})
