import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { generateEmbedCode } from '../utils/embedScriptGenerator'
import type { Video } from '../types/video'

const VIDEO_ID = 'vid-attr-1'

function makeVideo(extra: Record<string, unknown> = {}): Video {
  return {
    id: VIDEO_ID,
    title: 'VSL',
    video_url: 'https://cdn.exemplo.com/v.mp4',
    duration: 120,
    player_settings: { primary_color: '#000', ...extra },
  } as unknown as Video
}

function generate(video: Video, embedType: 'iframe' | 'script' = 'script'): string {
  return generateEmbedCode({
    video,
    embedUrl: `https://player.exemplo.com/?embed=${VIDEO_ID}`,
    embedType,
    resolvedWidth: '640px',
    resolvedHeight: null,
    heightPreset: '16:9',
    paddingTopMap: { '16:9': '56.25%' },
  })
}

/** Monta o embed na página e roda o script inline como a LP rodaria. */
function mount(code: string, dataXid?: string): HTMLIFrameElement {
  document.body.innerHTML = code
  if (dataXid !== undefined) {
    const container = document.getElementById(`vturb-player-${VIDEO_ID}`) || document.getElementById(`vturb-wrapper-${VIDEO_ID}`)
    container!.setAttribute('data-xid', dataXid)
  }
  const script = document.body.querySelector('script')!
  new Function(script.textContent || '')()
  return document.body.querySelector('iframe')!
}

function params(iframe: HTMLIFrameElement): URLSearchParams {
  return new URL(iframe.getAttribute('src')!).searchParams
}

function clearCookies() {
  document.cookie.split(';').forEach((c) => {
    const name = c.split('=')[0].trim()
    if (name) document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
  })
}

describe('script de embed: xid e UTMs da LP no src do iframe', () => {
  beforeEach(() => {
    localStorage.clear()
    clearCookies()
    delete (window as unknown as { SmartVSL?: unknown }).SmartVSL
    window.history.replaceState(null, '', '/lp')
  })
  afterEach(() => {
    document.body.innerHTML = ''
    clearCookies()
    delete (window as unknown as { SmartVSL?: unknown }).SmartVSL
    window.history.replaceState(null, '', '/')
  })

  it('acrescenta xid do cookie _eid e as utm_* codificadas, mantendo o sid', () => {  // VSL-06
    window.history.replaceState(
      null, '', '/lp?utm_source=fb&utm_medium=paid&utm_campaign=C%7C1&utm_content=Ad%7C120000000000000001&utm_term=S%7C2&fbclid=x',
    )
    document.cookie = '_eid=abc123DEF_-x; path=/'

    const p = params(mount(generate(makeVideo())))

    expect(p.get('embed')).toBe(VIDEO_ID)
    expect(p.get('sid')).toMatch(/^vis_/)
    expect(p.get('xid')).toBe('abc123DEF_-x')
    expect(p.get('utm_source')).toBe('fb')
    expect(p.get('utm_medium')).toBe('paid')
    expect(p.get('utm_campaign')).toBe('C|1')
    expect(p.get('utm_content')).toBe('Ad|120000000000000001')
    expect(p.get('utm_term')).toBe('S|2')
    expect(p.has('fbclid')).toBe(false)
  })

  it('funciona também no embed tipo iframe', () => {
    window.history.replaceState(null, '', '/lp?utm_source=fb')
    document.cookie = '_eid=abc123; path=/'
    const p = params(mount(generate(makeVideo(), 'iframe')))
    expect(p.get('xid')).toBe('abc123')
    expect(p.get('utm_source')).toBe('fb')
  })

  it('data-xid do container vence window.SmartVSL.xid e o cookie', () => {  // VSL-07
    document.cookie = '_eid=do_cookie; path=/'
    ;(window as unknown as { SmartVSL: { xid: string } }).SmartVSL = { xid: 'do_window' }
    expect(params(mount(generate(makeVideo()), 'do_atributo')).get('xid')).toBe('do_atributo')
  })

  it('window.SmartVSL.xid vence o cookie', () => {
    document.cookie = '_eid=do_cookie; path=/'
    ;(window as unknown as { SmartVSL: { xid: string } }).SmartVSL = { xid: 'do_window' }
    expect(params(mount(generate(makeVideo()))).get('xid')).toBe('do_window')
  })

  it('usa o cookie de player_settings.external_id_cookie quando configurado', () => {
    document.cookie = '_eid=errado; path=/'
    document.cookie = 'meu_tid=certo; path=/'
    expect(params(mount(generate(makeVideo({ external_id_cookie: 'meu_tid' })))).get('xid')).toBe('certo')
  })

  it('nome de cookie inseguro na configuração cai no _eid e não vai para o script', () => {
    document.cookie = '_eid=padrao; path=/'
    const code = generate(makeVideo({ external_id_cookie: "x';alert(1);//" }))
    expect(code).not.toContain('alert(1)')
    expect(params(mount(code)).get('xid')).toBe('padrao')
  })

  it('xid fora do formato aceito não é repassado', () => {
    document.cookie = '_eid=tem%20espaco; path=/'
    window.history.replaceState(null, '', '/lp?utm_source=fb')
    const p = params(mount(generate(makeVideo())))
    expect(p.has('xid')).toBe(false)
    expect(p.get('utm_source')).toBe('fb')
  })

  it('sem xid nem UTM só acrescenta o sid (comportamento anterior)', () => {
    const iframe = mount(generate(makeVideo()))
    const p = params(iframe)
    expect([...p.keys()].sort()).toEqual(['embed', 'sid', 'transparent'])
  })

  it('não duplica parâmetros que o src já tem', () => {
    window.history.replaceState(null, '', '/lp?utm_source=fb')
    document.cookie = '_eid=abc; path=/'
    const code = generate(makeVideo()).replace(`?embed=${VIDEO_ID}`, `?embed=${VIDEO_ID}&sid=vis_fixo&xid=ja_tinha`)
    const p = params(mount(code))
    expect(p.getAll('sid')).toEqual(['vis_fixo'])
    expect(p.getAll('xid')).toEqual(['ja_tinha'])
    expect(p.get('utm_source')).toBe('fb')
  })
})
