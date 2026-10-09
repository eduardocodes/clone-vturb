/**
 * Origem do espectador lida da URL do iframe: `xid` (id externo opaco, ex.: o `_eid`
 * da LP) e as `utm_*` da LP, repassadas pelo script de embed.
 * Contrato: contracts/export-v1.json (POST /videos/{id}/attribution).
 */

export const UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'] as const
export type UtmKey = (typeof UTM_KEYS)[number]

export type ViewerAttributionParams = { xid?: string } & Partial<Record<UtmKey, string>>

/** Mesmo formato que o backend aceita; xid fora dele seria recusado com 422 (perdendo as UTMs). */
export const XID_PATTERN = /^[A-Za-z0-9_-]{1,100}$/
export const UTM_MAX_LENGTH = 512

export function readViewerAttribution(search: string): ViewerAttributionParams | null {
  const params = new URLSearchParams(search)
  const result: ViewerAttributionParams = {}

  const xid = (params.get('xid') || '').trim()
  if (xid && XID_PATTERN.test(xid)) result.xid = xid

  for (const key of UTM_KEYS) {
    const value = (params.get(key) || '').trim()
    if (value) result[key] = value.slice(0, UTM_MAX_LENGTH)
  }

  return Object.keys(result).length > 0 ? result : null
}
