import { useEffect, useRef, useState } from 'react'

/** Subconjunto do hls.js que o player usa (facilita o teste com um falso). */
export interface HlsInstance {
  loadSource(url: string): void
  attachMedia(el: HTMLMediaElement): void
  destroy(): void
  on(event: string, cb: (event: string, data: { fatal: boolean }) => void): void
}

export interface HlsConstructor {
  new (config: Record<string, unknown>): HlsInstance
  isSupported(): boolean
  Events: { ERROR: string }
}

export type HlsSourceMode = 'mp4' | 'native' | 'hlsjs'

interface UseHlsSourceOptions {
  hlsUrl?: string | null
  mp4Url: string
  canPlayNativeHls?: () => boolean
  loadHls?: () => Promise<HlsConstructor>
}

let nativeHlsSupport: boolean | undefined

/** Safari/iOS tocam HLS direto no <video>; os demais precisam do hls.js (MSE). */
export function browserPlaysNativeHls(): boolean {
  if (nativeHlsSupport === undefined) {
    nativeHlsSupport =
      typeof document !== 'undefined' &&
      document.createElement('video').canPlayType('application/vnd.apple.mpegurl') !== ''
  }
  return nativeHlsSupport
}

// Import dinâmico do build light (sem legendas, áudio alternativo e DRM, que a VSL não usa):
// só é baixado quando o vídeo tem HLS
const defaultLoadHls = () => import('hls.js/light').then((m) => m.default as unknown as HlsConstructor)

/**
 * Liga a fonte do <video>: HLS nativo, hls.js ou o MP4 original (sem HLS ou em qualquer falha).
 * `ready` fica false enquanto o hls.js carrega, para o autoplay esperar a fonte certa.
 * Sem HLS, a fonte é o `src` do próprio JSX e o hook não mexe no elemento.
 */
export function useHlsSource(
  videoRef: React.RefObject<HTMLVideoElement | null>,
  { hlsUrl, mp4Url, canPlayNativeHls = browserPlaysNativeHls, loadHls = defaultLoadHls }: UseHlsSourceOptions
): { ready: boolean; mode: HlsSourceMode | null } {
  const [outcome, setOutcome] = useState<{ url: string; mode: 'hlsjs' | 'mp4' } | null>(null)
  const loadHlsRef = useRef(loadHls)
  const native = Boolean(hlsUrl) && canPlayNativeHls()

  useEffect(() => {
    loadHlsRef.current = loadHls
  })

  useEffect(() => {
    const el = videoRef.current
    if (!el || !hlsUrl) return
    let cancelled = false
    let hls: HlsInstance | null = null

    const fallbackToMp4 = () => {
      if (cancelled) return
      const resumeAt = el.currentTime
      const wasPlaying = !el.paused
      el.src = mp4Url
      if (resumeAt > 0) {
        el.addEventListener('loadedmetadata', () => (el.currentTime = resumeAt), { once: true })
      }
      if (wasPlaying) el.play()?.catch(() => {})
      setOutcome({ url: hlsUrl, mode: 'mp4' })
    }

    if (native) {
      el.src = hlsUrl
      el.addEventListener('error', fallbackToMp4, { once: true })
      return () => {
        cancelled = true
        el.removeEventListener('error', fallbackToMp4)
      }
    }

    loadHlsRef
      .current()
      .then((Hls) => {
        if (cancelled) return
        if (!Hls.isSupported()) {
          fallbackToMp4()
          return
        }
        const instance = new Hls({ capLevelToPlayerSize: true })
        hls = instance
        instance.on(Hls.Events.ERROR, (_event, data) => {
          if (!data?.fatal) return
          instance.destroy()
          hls = null
          fallbackToMp4()
        })
        instance.loadSource(hlsUrl)
        instance.attachMedia(el)
        setOutcome({ url: hlsUrl, mode: 'hlsjs' })
      })
      .catch(fallbackToMp4)

    return () => {
      cancelled = true
      hls?.destroy()
    }
  }, [videoRef, hlsUrl, mp4Url, native])

  if (!hlsUrl) return { ready: true, mode: 'mp4' }
  if (outcome?.url === hlsUrl) return { ready: true, mode: outcome.mode }
  if (native) return { ready: true, mode: 'native' }
  return { ready: false, mode: null }
}
