import { describe, it, expect, vi, afterEach } from 'vitest'
import { sendWatchRanges } from '../services/api'

describe('sendWatchRanges: envio dos trechos que sobrevive ao fechar a aba', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('usa sendBeacon com text/plain (sem preflight de CORS)', async () => {
    const beacon = vi.fn().mockReturnValue(true)
    vi.stubGlobal('navigator', { ...navigator, sendBeacon: beacon })

    sendWatchRanges('vid-1', { session_id: 's1', duration: 120, ranges: [[0, 10]] })

    expect(beacon).toHaveBeenCalledTimes(1)
    const [url, blob] = beacon.mock.calls[0]
    expect(url).toMatch(/\/videos\/vid-1\/watch$/)
    expect((blob as Blob).type).toContain('text/plain')
    expect(JSON.parse(await (blob as Blob).text())).toEqual({ session_id: 's1', duration: 120, ranges: [[0, 10]] })
  })

  it('sem sendBeacon, cai para fetch com keepalive', () => {
    vi.stubGlobal('navigator', { ...navigator, sendBeacon: undefined })
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    sendWatchRanges('vid-1', { session_id: 's1', duration: 10, ranges: [[0, 1]] })

    const [, init] = fetchMock.mock.calls[0]
    expect(init.keepalive).toBe(true)
    expect(init.headers['Content-Type']).toContain('text/plain')
  })
})
