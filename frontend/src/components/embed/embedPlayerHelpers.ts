import type { Video } from '../../types/video'

export function getOrCreateVisitorId(): string {
  try {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search)
      const urlSid = params.get('sid') || params.get('visitor_id')
      if (urlSid && urlSid.trim().length > 0) {
        const cleanSid = urlSid.trim()
        try { localStorage.setItem('vturb_visitor_id', cleanSid) } catch {}
        try { sessionStorage.setItem('vturb_visitor_id', cleanSid) } catch {}
        return cleanSid
      }
    }
    let id = ''
    try { id = localStorage.getItem('vturb_visitor_id') || '' } catch {}
    if (!id) {
      try { id = sessionStorage.getItem('vturb_visitor_id') || '' } catch {}
    }
    if (!id) {
      id = 'vis_' + Math.random().toString(36).substring(2, 11) + '_' + Date.now().toString(36)
    }
    try { localStorage.setItem('vturb_visitor_id', id) } catch {}
    try { sessionStorage.setItem('vturb_visitor_id', id) } catch {}
    return id
  } catch {
    return 'vis_' + Math.random().toString(36).substring(2, 9)
  }
}

/**
 * Verifica se o player e o iframe estão efetivamente visíveis na tela
 * (evita disparar impressão/autoplay quando o Quiz pré-carrega o iframe com display:none ou tamanho 0x0).
 */
export function isElementCurrentlyVisible(el?: HTMLElement | null): boolean {
  if (typeof window === 'undefined' || typeof document === 'undefined') return true
  if (document.visibilityState === 'hidden') return false
  if (window.innerWidth === 0 || window.innerHeight === 0) return false
  if (el) {
    const style = window.getComputedStyle(el)
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
      return false
    }
  }
  return true
}

export interface EmbedDimensionsConfig {
  effectiveRatio: '16:9' | '9:16' | '4:3' | string
  configuredWidth?: string | null
  isTransparent: boolean
  isInsideIframe: boolean
}

export function parseEmbedDimensions(video: Video | null): EmbedDimensionsConfig {
  const queryParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : new URLSearchParams()
  const rawRatio = queryParams.get('ratio') || queryParams.get('aspect_ratio')
  const effectiveRatio = (rawRatio === '9:16' || rawRatio === '9-16' || rawRatio === '9/16')
    ? '9:16'
    : (rawRatio === '4:3' ? '4:3' : (rawRatio === '16:9' ? '16:9' : video?.player_settings?.aspect_ratio || '16:9'))
  const configuredWidth = queryParams.get('width') || queryParams.get('max_width') || video?.player_settings?.default_width

  const trParam = queryParams.get('transparent')
  const isTransparent = trParam !== null
    ? (trParam === '1' || trParam === 'true')
    : (video?.player_settings?.transparent_background ?? true)

  const isInsideIframe = typeof window !== 'undefined' && window !== window.top

  return { effectiveRatio, configuredWidth, isTransparent, isInsideIframe }
}

interface ComputeContainerStyleParams {
  isFloatingActive: boolean
  isFullscreen: boolean
  isTransparent: boolean
  isVideoReady: boolean
  floatingConfig?: {
    enabled?: boolean
    position?: 'bottom-right' | 'bottom-left' | string
    width?: number
    closeable?: boolean
  } | null
  effectiveRatio: string
  configuredWidth?: string | null
  isInsideIframe: boolean
  borderRadius?: number
}

export function computeEmbedContainerStyle({
  isFloatingActive,
  isFullscreen,
  isTransparent,
  isVideoReady,
  floatingConfig,
  effectiveRatio,
  configuredWidth,
  isInsideIframe,
  borderRadius = 0,
}: ComputeContainerStyleParams): React.CSSProperties {
  const floatWidth = floatingConfig?.width || 320
  const floatHeight = Math.round((floatWidth * 9) / 16)

  const maxWidth = isFullscreen
    ? 'none'
    : isFloatingActive
    ? undefined
    : !isInsideIframe
    ? (configuredWidth
        ? (configuredWidth.endsWith('px') || configuredWidth.endsWith('%') ? configuredWidth : `${configuredWidth}px`)
        : (effectiveRatio === '9:16' ? '450px' : '100%'))
    : '100%'

  const aspectRatio = isFullscreen
    ? undefined
    : isFloatingActive
    ? '16/9'
    : (isInsideIframe ? undefined : (effectiveRatio === '9:16' ? '9/16' : effectiveRatio === '4:3' ? '4/3' : undefined))

  return {
    position: isFloatingActive ? 'fixed' : 'relative',
    bottom: isFloatingActive ? '32px' : undefined,
    right: isFloatingActive ? (floatingConfig?.position === 'bottom-left' ? undefined : '56px') : undefined,
    left: isFloatingActive ? (floatingConfig?.position === 'bottom-left' ? '32px' : undefined) : undefined,
    width: isFullscreen ? '100vw' : isFloatingActive ? `${floatWidth}px` : '100%',
    maxWidth,
    aspectRatio,
    margin: isFloatingActive ? undefined : '0 auto',
    height: isFullscreen ? '100vh' : isFloatingActive ? `${floatHeight}px` : '100%',
    minHeight: isFullscreen ? '100vh' : isFloatingActive ? `${floatHeight}px` : '100%',
    maxHeight: isFullscreen
      ? 'none'
      : isFloatingActive
      ? `${floatHeight}px`
      : (!isInsideIframe && effectiveRatio === '9:16' ? '92vh' : undefined),
    zIndex: isFloatingActive ? 9999 : 1,
    borderRadius: isFullscreen ? '0px' : isFloatingActive ? '16px' : `${borderRadius}px`,
    boxShadow: isFloatingActive && !isFullscreen
      ? '0 20px 45px rgba(0, 0, 0, 0.75), 0 0 0 2px rgba(255, 255, 255, 0.1)'
      : 'none',
    transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
    background: isFullscreen ? '#000000' : isTransparent && isVideoReady ? 'transparent' : '#000000',
    overflow: 'hidden',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  }
}
