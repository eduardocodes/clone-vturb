import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useHlsSource, type HlsConstructor } from '../components/embed/useHlsSource'

const HLS = 'https://video.exemplo.com/videos/x/hls/1/master.m3u8'
const MP4 = 'https://video.exemplo.com/videos/x/source.mp4'

type Handler = (event: string, data: { fatal: boolean }) => void

function fakeHls(supported = true) {
  const instances: FakeHls[] = []
  class FakeHls {
    static isSupported = () => supported
    static Events = { ERROR: 'hlsError' }
    config: unknown
    handlers: Record<string, Handler> = {}
    loadSource = vi.fn()
    attachMedia = vi.fn()
    destroy = vi.fn()
    constructor(config: unknown) {
      this.config = config
      instances.push(this)
    }
    on(event: string, cb: Handler) {
      this.handlers[event] = cb
    }
  }
  return { Hls: FakeHls as unknown as HlsConstructor, instances }
}

function setup(opts: { hlsUrl?: string | null; native?: boolean; loadHls?: () => Promise<HlsConstructor> }) {
  const el = document.createElement('video')
  const ref = { current: el }
  const hook = renderHook(() =>
    useHlsSource(ref, {
      hlsUrl: opts.hlsUrl,
      mp4Url: MP4,
      canPlayNativeHls: () => opts.native ?? false,
      loadHls: opts.loadHls,
    })
  )
  return { el, ...hook }
}

describe('useHlsSource', () => {
  beforeEach(() => vi.clearAllMocks())

  it('sem HLS usa o MP4 e já está pronto, sem carregar o hls.js', () => {
    const loadHls = vi.fn()
    const { result } = setup({ hlsUrl: null, loadHls })
    expect(result.current).toEqual({ ready: true, mode: 'mp4' })
    expect(loadHls).not.toHaveBeenCalled()
  })

  it('navegador com HLS nativo (Safari/iOS) toca a playlist direto', () => {
    const loadHls = vi.fn()
    const { el, result } = setup({ hlsUrl: HLS, native: true, loadHls })
    expect(el.src).toBe(HLS)
    expect(result.current).toEqual({ ready: true, mode: 'native' })
    expect(loadHls).not.toHaveBeenCalled()
  })

  it('HLS nativo com erro volta para o MP4', () => {
    const { el, result } = setup({ hlsUrl: HLS, native: true })
    act(() => {
      el.dispatchEvent(new Event('error'))
    })
    expect(el.src).toBe(MP4)
    expect(result.current.mode).toBe('mp4')
  })

  it('nos outros navegadores carrega o hls.js e anexa ao vídeo', async () => {
    const { Hls, instances } = fakeHls()
    const { el, result } = setup({ hlsUrl: HLS, loadHls: () => Promise.resolve(Hls) })

    expect(result.current.ready).toBe(false) // autoplay espera a fonte
    await waitFor(() => expect(result.current).toEqual({ ready: true, mode: 'hlsjs' }))
    const hls = instances[0]
    expect(hls.config).toMatchObject({ capLevelToPlayerSize: true })
    expect(hls.loadSource).toHaveBeenCalledWith(HLS)
    expect(hls.attachMedia).toHaveBeenCalledWith(el)
  })

  it('sem suporte a MSE cai no MP4', async () => {
    const { Hls, instances } = fakeHls(false)
    const { el, result } = setup({ hlsUrl: HLS, loadHls: () => Promise.resolve(Hls) })
    await waitFor(() => expect(result.current).toEqual({ ready: true, mode: 'mp4' }))
    expect(el.src).toBe(MP4)
    expect(instances).toHaveLength(0)
  })

  it('falha ao baixar o hls.js cai no MP4', async () => {
    const { el, result } = setup({ hlsUrl: HLS, loadHls: () => Promise.reject(new Error('offline')) })
    await waitFor(() => expect(result.current).toEqual({ ready: true, mode: 'mp4' }))
    expect(el.src).toBe(MP4)
  })

  it('erro fatal do hls.js volta para o MP4 no mesmo ponto', async () => {
    const { Hls, instances } = fakeHls()
    const { el, result } = setup({ hlsUrl: HLS, loadHls: () => Promise.resolve(Hls) })
    await waitFor(() => expect(result.current.mode).toBe('hlsjs'))

    act(() => instances[0].handlers.hlsError('hlsError', { fatal: true }))

    expect(instances[0].destroy).toHaveBeenCalled()
    expect(el.src).toBe(MP4)
    expect(result.current.mode).toBe('mp4')
  })

  it('erro não fatal é tratado pelo próprio hls.js', async () => {
    const { Hls, instances } = fakeHls()
    const { el, result } = setup({ hlsUrl: HLS, loadHls: () => Promise.resolve(Hls) })
    await waitFor(() => expect(result.current.mode).toBe('hlsjs'))

    act(() => instances[0].handlers.hlsError('hlsError', { fatal: false }))

    expect(instances[0].destroy).not.toHaveBeenCalled()
    expect(el.getAttribute('src')).toBeNull()
  })

  it('desmontar destrói o hls.js', async () => {
    const { Hls, instances } = fakeHls()
    const { result, unmount } = setup({ hlsUrl: HLS, loadHls: () => Promise.resolve(Hls) })
    await waitFor(() => expect(result.current.mode).toBe('hlsjs'))
    unmount()
    expect(instances[0].destroy).toHaveBeenCalled()
  })

  it('desmontar antes do hls.js carregar não anexa nada', async () => {
    const { Hls, instances } = fakeHls()
    let resolve!: (h: HlsConstructor) => void
    const { unmount } = setup({ hlsUrl: HLS, loadHls: () => new Promise((r) => (resolve = r)) })
    unmount()
    await act(async () => resolve(Hls))
    expect(instances).toHaveLength(0)
  })
})
