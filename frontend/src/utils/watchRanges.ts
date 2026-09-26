import type { WatchRanges } from '../types/analytics'

/** Salto entre dois timeupdate considerado reprodução contínua (cobre velocidade até ~4x). */
const MAX_CONTINUOUS_STEP_SECONDS = 3
/** Buracos menores que isso são unidos (mesma regra do backend). */
const MERGE_GAP_SECONDS = 0.5
/** Limite de trechos aceito pelo backend. */
const MAX_RANGES = 500

function round(n: number): number {
  return Math.round(n * 100) / 100
}

function mergeRanges(ranges: WatchRanges): WatchRanges {
  const sorted = [...ranges].sort((a, b) => a[0] - b[0])
  const merged: WatchRanges = []
  for (const [start, end] of sorted) {
    const last = merged[merged.length - 1]
    if (last && start <= last[1] + MERGE_GAP_SECONDS) {
      last[1] = Math.max(last[1], end)
    } else {
      merged.push([start, end])
    }
  }
  return merged
}

/**
 * Acumula os trechos do vídeo realmente assistidos a partir do currentTime de cada
 * timeupdate. Saltos (seek) abrem um trecho novo: o pedaço pulado não conta.
 */
export class WatchRangeTracker {
  private closed: WatchRanges = []
  private current: [number, number] | null = null
  private lastSent = ''

  observe(time: number): void {
    if (!Number.isFinite(time) || time < 0) return
    if (this.current) {
      const step = time - this.current[1]
      if (step >= 0 && step <= MAX_CONTINUOUS_STEP_SECONDS) {
        this.current[1] = time
        return
      }
      this.closeCurrent()
    }
    this.current = [time, time]
  }

  private closeCurrent(): void {
    if (this.current && this.current[1] > this.current[0]) {
      this.closed = mergeRanges([...this.closed, [this.current[0], this.current[1]]])
      if (this.closed.length > MAX_RANGES) {
        // Une os trechos mais próximos até caber: preserva a forma da curva
        this.closed = mergeClosest(this.closed, MAX_RANGES)
      }
    }
    this.current = null
  }

  ranges(): WatchRanges {
    const all = this.current && this.current[1] > this.current[0]
      ? mergeRanges([...this.closed, [this.current[0], this.current[1]]])
      : mergeRanges(this.closed)
    const bounded = all.length > MAX_RANGES ? mergeClosest(all, MAX_RANGES) : all
    return bounded.map(([s, e]) => [round(s), round(e)])
  }

  /** Trechos atuais se mudaram desde a última chamada; senão null. */
  takeIfChanged(): WatchRanges | null {
    const ranges = this.ranges()
    if (ranges.length === 0) return null
    const key = JSON.stringify(ranges)
    if (key === this.lastSent) return null
    this.lastSent = key
    return ranges
  }
}

function mergeClosest(ranges: WatchRanges, max: number): WatchRanges {
  const result = ranges.map(([s, e]) => [s, e] as [number, number])
  while (result.length > max) {
    let best = 1
    let bestGap = Infinity
    for (let i = 1; i < result.length; i++) {
      const gap = result[i][0] - result[i - 1][1]
      if (gap < bestGap) {
        bestGap = gap
        best = i
      }
    }
    result[best - 1][1] = Math.max(result[best - 1][1], result[best][1])
    result.splice(best, 1)
  }
  return result
}
