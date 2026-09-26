import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

const sendWatchRanges = vi.fn()
const sendTelemetryEvent = vi.fn()
vi.mock('../services/api', () => ({
  sendWatchRanges: (...a: unknown[]) => sendWatchRanges(...a),
  sendTelemetryEvent: (...a: unknown[]) => sendTelemetryEvent(...a),
}))

import { useVideoTelemetry } from '../hooks/useVideoTelemetry'
import type { Video } from '../types/video'

const video = { id: 'v1', title: 'V', video_url: 'x', duration: 100, player_settings: {}, created_at: '', updated_at: '' } as unknown as Video

function setup() {
  return renderHook(() => useVideoTelemetry({ video, videoId: 'v1', visitorId: 'vis-1', setShowCta: () => {} }))
}

function watch(result: ReturnType<typeof setup>['result'], from: number, to: number) {
  for (let t = from; t <= to; t += 0.25) result.current.handleTimeUpdateProgress(t, 100)
}

describe('useVideoTelemetry: envio dos trechos assistidos', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    sendWatchRanges.mockClear()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('envia a cada 30s enquanto houver novidade', () => {
    const { result } = setup()
    act(() => watch(result, 0, 10))

    act(() => vi.advanceTimersByTime(30_000))
    expect(sendWatchRanges).toHaveBeenCalledWith('v1', { session_id: 'vis-1', duration: 100, ranges: [[0, 10]] })

    act(() => vi.advanceTimersByTime(30_000))
    expect(sendWatchRanges).toHaveBeenCalledTimes(1)
  })

  it('envia na hora quando a aba fica oculta ou a página fecha', () => {
    const { result } = setup()
    act(() => watch(result, 0, 5))

    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'))
    })
    expect(sendWatchRanges).toHaveBeenCalledTimes(1)

    act(() => watch(result, 5, 8))
    act(() => {
      window.dispatchEvent(new Event('pagehide'))
    })
    expect(sendWatchRanges).toHaveBeenLastCalledWith('v1', { session_id: 'vis-1', duration: 100, ranges: [[0, 8]] })
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true })
  })

  it('envia ao terminar o vídeo', () => {
    const { result } = setup()
    act(() => watch(result, 95, 100))
    act(() => result.current.handleEndedTelemetry(100))
    expect(sendWatchRanges).toHaveBeenCalledWith('v1', expect.objectContaining({ ranges: [[95, 100]] }))
  })
})
