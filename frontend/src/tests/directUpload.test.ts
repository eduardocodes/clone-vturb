import { describe, it, expect, vi } from 'vitest'
import { uploadMedia, type UploadApi, type UploadTransport } from '../services/directUpload'

const MB = 1024 * 1024

function fakeFile(size: number, name = 'vsl.mp4', type = 'video/mp4'): File {
  // Blob com o tamanho certo sem alocar o conteúdo de verdade
  const blob = new Blob([new Uint8Array(size)], { type })
  return new File([blob], name, { type })
}

function fakeApi(overrides: Partial<UploadApi> = {}): UploadApi {
  return {
    config: vi.fn().mockResolvedValue({ direct: true, max_video_bytes: 4096 * MB, max_image_bytes: 10 * MB, part_size: 5 * MB }),
    init: vi.fn().mockResolvedValue({
      method: 'multipart',
      key: 'videos/11111111-1111-1111-1111-111111111111/source.mp4',
      upload_id: 'up-1',
      part_size: 5 * MB,
      part_count: 3,
    }),
    signParts: vi.fn().mockImplementation(async ({ part_numbers }: { part_numbers: number[] }) => ({
      urls: Object.fromEntries(part_numbers.map((n) => [String(n), `https://s3/part/${n}`])),
    })),
    complete: vi.fn().mockImplementation(async ({ key, size }: { key: string; size: number }) => ({
      key,
      url: `https://video.exemplo.com/${key}`,
      size,
    })),
    abort: vi.fn().mockResolvedValue(undefined),
    legacyUpload: vi.fn().mockResolvedValue({ filename: 'vsl.mp4', url: 'http://api/static/uploads/x.mp4' }),
    ...overrides,
  }
}

function fakeTransport(overrides: Partial<UploadTransport> = {}): UploadTransport {
  return {
    putPart: vi.fn().mockImplementation(async (url: string, blob: Blob, onProgress: (n: number) => void) => {
      onProgress(blob.size)
      return `"etag-${url.split('/').pop()}"`
    }),
    put: vi.fn().mockImplementation(async (_url: string, blob: Blob, _h: Record<string, string>, onProgress: (n: number) => void) => {
      onProgress(blob.size)
    }),
    ...overrides,
  }
}

const noSleep = () => Promise.resolve()

describe('uploadMedia: vídeo em partes direto no storage', () => {
  it('envia todas as partes, completa com os ETags em ordem e devolve a chave', async () => {
    const api = fakeApi()
    const transport = fakeTransport()
    const file = fakeFile(12 * MB)

    const res = await uploadMedia(file, 'video', { api, transport, sleep: noSleep })

    expect(api.init).toHaveBeenCalledWith({ kind: 'video', filename: 'vsl.mp4', content_type: 'video/mp4', size: 12 * MB })
    expect(transport.putPart).toHaveBeenCalledTimes(3)
    const sizes = (transport.putPart as any).mock.calls.map((c: any[]) => (c[1] as Blob).size)
    expect(sizes.sort((a: number, b: number) => a - b)).toEqual([2 * MB, 5 * MB, 5 * MB])
    const completeArgs = (api.complete as any).mock.calls[0][0]
    expect(completeArgs.parts.map((p: any) => p.part_number).sort()).toEqual([1, 2, 3])
    expect(completeArgs.size).toBe(12 * MB)
    expect(res).toEqual({
      url: 'https://video.exemplo.com/videos/11111111-1111-1111-1111-111111111111/source.mp4',
      storageKey: 'videos/11111111-1111-1111-1111-111111111111/source.mp4',
      sizeBytes: 12 * MB,
    })
  })

  it('informa progresso agregado até 100%', async () => {
    const progress: number[] = []
    await uploadMedia(fakeFile(12 * MB), 'video', {
      api: fakeApi(),
      transport: fakeTransport(),
      sleep: noSleep,
      onProgress: (p) => progress.push(p),
    })
    expect(progress.at(-1)).toBe(100)
    expect(progress).toEqual([...progress].sort((a, b) => a - b))
  })

  it('reenvia uma parte que falhou, com URL assinada de novo', async () => {
    let attempts = 0
    const transport = fakeTransport({
      putPart: vi.fn().mockImplementation(async (url: string, blob: Blob, onProgress: (n: number) => void) => {
        if (url.endsWith('/2') && attempts++ < 2) throw new Error('rede caiu')
        onProgress(blob.size)
        return '"ok"'
      }),
    })
    const api = fakeApi()

    await uploadMedia(fakeFile(12 * MB), 'video', { api, transport, sleep: noSleep })

    expect(transport.putPart).toHaveBeenCalledTimes(5)
    expect(api.complete).toHaveBeenCalledTimes(1)
    const signedForPart2 = (api.signParts as any).mock.calls.filter((c: any[]) => c[0].part_numbers.includes(2))
    expect(signedForPart2.length).toBeGreaterThanOrEqual(2)
  })

  it('desiste depois de 3 tentativas e cancela o multipart', async () => {
    const api = fakeApi()
    const transport = fakeTransport({ putPart: vi.fn().mockRejectedValue(new Error('rede caiu')) })

    await expect(uploadMedia(fakeFile(12 * MB), 'video', { api, transport, sleep: noSleep })).rejects.toThrow()

    expect(api.abort).toHaveBeenCalledWith({ key: expect.any(String), upload_id: 'up-1' })
    expect(api.complete).not.toHaveBeenCalled()
  })

  it('cancelar pelo AbortSignal aborta o multipart', async () => {
    const controller = new AbortController()
    const api = fakeApi()
    const transport = fakeTransport({
      putPart: vi.fn().mockImplementation(async () => {
        controller.abort()
        throw new DOMException('cancelado', 'AbortError')
      }),
    })

    await expect(
      uploadMedia(fakeFile(12 * MB), 'video', { api, transport, sleep: noSleep, signal: controller.signal })
    ).rejects.toThrow()
    expect(api.abort).toHaveBeenCalled()
  })

  it('não passa de N envios simultâneos', async () => {
    let active = 0
    let peak = 0
    const api = fakeApi({
      init: vi.fn().mockResolvedValue({ method: 'multipart', key: 'videos/k/source.mp4', upload_id: 'u', part_size: 1 * MB, part_count: 10 }),
    })
    const transport = fakeTransport({
      putPart: vi.fn().mockImplementation(async (_u: string, blob: Blob, onProgress: (n: number) => void) => {
        active++
        peak = Math.max(peak, active)
        await new Promise((r) => setTimeout(r, 1))
        active--
        onProgress(blob.size)
        return '"e"'
      }),
    })

    await uploadMedia(fakeFile(10 * MB), 'video', { api, transport, sleep: noSleep, concurrency: 3 })

    expect(peak).toBeLessThanOrEqual(3)
    expect(transport.putPart).toHaveBeenCalledTimes(10)
  })
})

describe('uploadMedia: capa e fallback', () => {
  it('capa usa PUT único com o Content-Type assinado', async () => {
    const api = fakeApi({
      init: vi.fn().mockResolvedValue({
        method: 'put',
        key: 'thumbs/abc.jpg',
        url: 'https://s3/put',
        headers: { 'Content-Type': 'image/jpeg' },
        public_url: 'https://video.exemplo.com/thumbs/abc.jpg',
      }),
    })
    const transport = fakeTransport()

    const res = await uploadMedia(fakeFile(1000, 'capa.jpg', 'image/jpeg'), 'thumbnail', { api, transport, sleep: noSleep })

    expect(transport.put).toHaveBeenCalledWith('https://s3/put', expect.any(Blob), { 'Content-Type': 'image/jpeg' }, expect.any(Function), undefined)
    expect(res).toEqual({ url: 'https://video.exemplo.com/thumbs/abc.jpg' })
  })

  it('sem upload direto disponível, usa o envio antigo pelo backend', async () => {
    const api = fakeApi({ config: vi.fn().mockResolvedValue({ direct: false, max_video_bytes: 0, max_image_bytes: 0, part_size: 0 }) })

    const res = await uploadMedia(fakeFile(1000), 'video', { api, transport: fakeTransport(), sleep: noSleep })

    expect(api.legacyUpload).toHaveBeenCalled()
    expect(api.init).not.toHaveBeenCalled()
    expect(res).toEqual({ url: 'http://api/static/uploads/x.mp4' })
  })

  it('recusa antes de enviar quando passa do limite', async () => {
    const api = fakeApi({ config: vi.fn().mockResolvedValue({ direct: true, max_video_bytes: 5 * MB, max_image_bytes: MB, part_size: MB }) })

    await expect(uploadMedia(fakeFile(6 * MB), 'video', { api, transport: fakeTransport(), sleep: noSleep })).rejects.toThrow(/limite/i)
    expect(api.init).not.toHaveBeenCalled()
  })
})
