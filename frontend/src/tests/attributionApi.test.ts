import { describe, it, expect, vi, afterEach } from 'vitest'
import { sendViewerAttribution } from '../services/attributionApi'
import { getApiBaseUrl } from '../services/apiConfig'

describe('sendViewerAttribution', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('faz POST JSON com keepalive em /videos/{id}/attribution', () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    sendViewerAttribution('v1', { session_id: 'vis_x', xid: 'abc' })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(`${getApiBaseUrl()}/videos/v1/attribution`)
    expect(init.method).toBe('POST')
    expect(init.keepalive).toBe(true)
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(JSON.parse(init.body)).toEqual({ session_id: 'vis_x', xid: 'abc' })
  })

  it('engole falha de rede (fire-and-forget)', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    expect(() => sendViewerAttribution('v1', { session_id: 'vis_x' })).not.toThrow()
    await new Promise((r) => setTimeout(r, 0))
  })

  it('engole fetch que lança de forma síncrona', () => {
    vi.stubGlobal('fetch', vi.fn(() => { throw new TypeError('bloqueado') }))
    expect(() => sendViewerAttribution('v1', { session_id: 'vis_x' })).not.toThrow()
  })
})
