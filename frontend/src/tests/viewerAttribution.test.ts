import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

const sendTelemetryEvent = vi.fn()
const sendViewerAttribution = vi.fn()
vi.mock('../services/api', () => ({
  sendWatchRanges: vi.fn(),
  sendTelemetryEvent: (...a: unknown[]) => sendTelemetryEvent(...a),
}))
vi.mock('../services/attributionApi', () => ({
  sendViewerAttribution: (...a: unknown[]) => sendViewerAttribution(...a),
}))

import { readViewerAttribution } from '../components/embed/viewerAttribution'
import { useVideoTelemetry } from '../hooks/useVideoTelemetry'
import type { Video } from '../types/video'

describe('readViewerAttribution', () => {
  it('lê xid e as cinco utm_* da URL do iframe', () => {
    const search =
      '?embed=v1&sid=vis_x&xid=abc123&utm_source=fb&utm_medium=paid&utm_campaign=C%7C1' +
      '&utm_content=Ad%7C120000000000000001&utm_term=S%7C2'
    expect(readViewerAttribution(search)).toEqual({
      xid: 'abc123',
      utm_source: 'fb',
      utm_medium: 'paid',
      utm_campaign: 'C|1',
      utm_content: 'Ad|120000000000000001',
      utm_term: 'S|2',
    })
  })

  it('devolve null sem xid nem utm', () => {
    expect(readViewerAttribution('?embed=v1&sid=vis_x')).toBeNull()
    expect(readViewerAttribution('')).toBeNull()
    expect(readViewerAttribution('?xid=&utm_source=')).toBeNull()
  })

  it('só com UTM manda só as UTMs presentes', () => {
    expect(readViewerAttribution('?utm_source=fb')).toEqual({ utm_source: 'fb' })
  })

  it('descarta xid inválido mas mantém as UTMs (o servidor recusaria tudo com 422)', () => {
    expect(readViewerAttribution('?xid=tem%20espaco&utm_source=fb')).toEqual({ utm_source: 'fb' })
    expect(readViewerAttribution(`?xid=${'a'.repeat(101)}`)).toBeNull()
    expect(readViewerAttribution(`?xid=${'a'.repeat(100)}`)).toEqual({ xid: 'a'.repeat(100) })
  })

  it('corta UTM em 512 caracteres', () => {
    const r = readViewerAttribution(`?utm_content=${'c'.repeat(900)}`)
    expect(r?.utm_content).toHaveLength(512)
  })
})

describe('useVideoTelemetry: origem do espectador junto da impressão', () => {
  const video = { id: 'v1', title: 'V', video_url: 'x', duration: 100, player_settings: {}, created_at: '', updated_at: '' } as unknown as Video
  const setup = () =>
    renderHook(() => useVideoTelemetry({ video, videoId: 'v1', visitorId: 'vis-1', setShowCta: () => {} }))

  beforeEach(() => {
    sendTelemetryEvent.mockClear()
    sendViewerAttribution.mockClear()
  })
  afterEach(() => {
    window.history.replaceState(null, '', '/')
  })

  it('envia uma vez por carregamento, com o session_id do player', () => {
    window.history.replaceState(null, '', '/?embed=v1&xid=abc123&utm_source=fb')
    const { result } = setup()

    act(() => result.current.trackImpression())
    act(() => result.current.trackImpression())

    expect(sendViewerAttribution).toHaveBeenCalledTimes(1)
    expect(sendViewerAttribution).toHaveBeenCalledWith('v1', { session_id: 'vis-1', xid: 'abc123', utm_source: 'fb' })
    expect(sendTelemetryEvent).toHaveBeenCalledTimes(1)
  })

  it('não envia nada sem xid nem utm', () => {
    window.history.replaceState(null, '', '/?embed=v1&sid=vis-1')
    const { result } = setup()
    act(() => result.current.trackImpression())
    expect(sendViewerAttribution).not.toHaveBeenCalled()
    expect(sendTelemetryEvent).toHaveBeenCalledTimes(1)
  })

  it('erro ao enviar a origem não quebra a impressão', () => {
    window.history.replaceState(null, '', '/?xid=abc')
    sendViewerAttribution.mockImplementationOnce(() => {
      throw new Error('falhou')
    })
    const { result } = setup()
    expect(() => act(() => result.current.trackImpression())).not.toThrow()
    expect(sendTelemetryEvent).toHaveBeenCalledTimes(1)
  })
})
