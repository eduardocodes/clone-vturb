import type { RetentionCurve, VideoMetrics } from '../../../types/video'

export const formatTime = (secs: number): string => {
  const m = Math.floor(secs / 60)
  const s = Math.floor(secs % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export const getTimeTicks = (duration: number): string[] => [
  formatTime(0),
  formatTime(Math.round(duration * 0.27)),
  formatTime(Math.round(duration * 0.54)),
  formatTime(Math.round(duration * 0.81)),
  formatTime(duration),
]

export const hourlyTicks = ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', '23:00']

export interface RetentionValues {
  0: number
  25: number
  50: number
  75: number
  100: number
}

export const getRetentionValues = (metrics: VideoMetrics, totalPlays: number): RetentionValues => ({
  0: totalPlays > 0 ? 100 : 0,
  25: totalPlays > 0 ? ((metrics.retention['25%'] || 0) / totalPlays) * 100 : 0,
  50: totalPlays > 0 ? ((metrics.retention['50%'] || 0) / totalPlays) * 100 : 0,
  75: totalPlays > 0 ? ((metrics.retention['75%'] || 0) / totalPlays) * 100 : 0,
  100: totalPlays > 0 ? ((metrics.retention['100%'] || 0) / totalPlays) * 100 : 0,
})

export const getInterpolatedRetention = (
  pct: number,
  retentionValues: RetentionValues,
  totalPlays: number,
  audienceBase: number
) => {
  if (totalPlays === 0) return { retention: 0, audience: 0 }
  let ret = 0

  if (pct <= 25) {
    const factor = pct / 25
    ret = retentionValues[0] + factor * (retentionValues[25] - retentionValues[0])
  } else if (pct <= 50) {
    const factor = (pct - 25) / 25
    ret = retentionValues[25] + factor * (retentionValues[50] - retentionValues[25])
  } else if (pct <= 75) {
    const factor = (pct - 50) / 25
    ret = retentionValues[50] + factor * (retentionValues[75] - retentionValues[50])
  } else {
    const factor = (pct - 75) / 25
    ret = retentionValues[75] + factor * (retentionValues[100] - retentionValues[75])
  }

  const finalRet = Math.max(0, Math.min(100, ret))
  const aud = Math.round((finalRet / 100) * (audienceBase || 0))

  return {
    retention: finalRet,
    audience: Math.max(0, aud),
  }
}

// Mapeamento Y para coordenadas SVG (altura 200, base y=190, topo y=15)
export const getYCoordinate = (percent: number): number => {
  return 190 - (percent / 100) * 175
}

export const generateRetentionPaths = (retentionValues: RetentionValues) => {
  const p0 = { x: 0, y: getYCoordinate(retentionValues[0]) }
  const p25 = { x: 250, y: getYCoordinate(retentionValues[25]) }
  const p50 = { x: 500, y: getYCoordinate(retentionValues[50]) }
  const p75 = { x: 750, y: getYCoordinate(retentionValues[75]) }
  const p100 = { x: 1000, y: getYCoordinate(retentionValues[100]) }

  const retentionPathD = `M ${p0.x},${p0.y} C 125,${p0.x === 0 ? p0.y : p0.y} 125,${p25.y} ${p25.x},${p25.y} C 375,${p25.y} 375,${p50.y} ${p50.x},${p50.y} C 625,${p50.y} 625,${p75.y} ${p75.x},${p75.y} C 875,${p75.y} 875,${p100.y} ${p100.x},${p100.y}`
  const retentionAreaD = `${retentionPathD} L 1000,190 L 0,190 Z`

  return { retentionPathD, retentionAreaD }
}

export const generateHourlyPaths = (
  hourlyList: Array<{ hour: number; label: string; impressions: number; plays: number }>,
  maxActivity: number
) => {
  const hourlyPoints = hourlyList.map((item, idx) => {
    const x = (idx / 23) * 1000
    const pct = (item.plays / maxActivity) * 100
    const y = getYCoordinate(pct)
    return { x, y }
  })
  const hourlyPathD = hourlyPoints.length > 0
    ? hourlyPoints.reduce((acc, pt, i) => (i === 0 ? `M ${pt.x},${pt.y}` : `${acc} L ${pt.x},${pt.y}`), '')
    : 'M 0,190 L 1000,190'
  const hourlyAreaD = `${hourlyPathD} L 1000,190 L 0,190 Z`

  return { hourlyPathD, hourlyAreaD }
}

// --- Curva por segundo (retention_curve do backend) --------------------------------

/** Retenção (0-100) no ponto `pct` (0-100) do vídeo de `duration` segundos. */
export const curveRetentionAt = (curve: RetentionCurve, pct: number, duration: number): number => {
  const values = curve.values
  if (!values.length || curve.sessions <= 0 || duration <= 0) return 0
  const second = (Math.max(0, Math.min(100, pct)) / 100) * duration
  const pos = second / curve.bucket_seconds
  if (pos > values.length - 1) {
    // Depois do último trecho com dado: ninguém assistiu
    return pos < values.length ? Math.max(0, Math.min(100, values[values.length - 1] * 100)) : 0
  }
  const i = Math.floor(pos)
  const next = Math.min(values.length - 1, i + 1)
  const value = values[i] + (values[next] - values[i]) * (pos - i)
  return Math.max(0, Math.min(100, value * 100))
}

/** Caminho SVG da curva com o eixo X no tempo do vídeo (0 a `duration`). */
export const generateCurvePaths = (curve: RetentionCurve, duration: number) => {
  const values = curve.values
  if (!values.length || curve.sessions <= 0 || duration <= 0) {
    return { retentionPathD: 'M 0,190 L 1000,190', retentionAreaD: 'M 0,190 L 1000,190 L 1000,190 L 0,190 Z' }
  }
  const toX = (second: number) => Math.round(Math.min(1, second / duration) * 10000) / 10
  const toY = (fraction: number) => Math.round(getYCoordinate(Math.max(0, Math.min(100, fraction * 100))) * 100) / 100
  const parts = values.map((v, idx) => `${idx === 0 ? 'M' : 'L'} ${toX(idx * curve.bucket_seconds)},${toY(v)}`)
  const lastSecond = values.length * curve.bucket_seconds
  if (lastSecond < duration) {
    // Queda para zero logo depois do último trecho assistido, e chão até o fim
    parts.push(`L ${toX(lastSecond)},190`, 'L 1000,190')
  }
  const retentionPathD = parts.join(' ')
  return { retentionPathD, retentionAreaD: `${retentionPathD} L 1000,190 L 0,190 Z` }
}
