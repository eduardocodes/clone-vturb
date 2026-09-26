import { describe, it, expect } from 'vitest'
import {
  resolveSmartProgress,
  toVisualFraction,
  mapChapterSegments,
} from '../utils/smartProgress'
import type { ChapterItem } from '../types/video'

const on = (intensity: 'suave' | 'medio' | 'forte') => ({ enabled: true, intensity })

describe('smartProgress - curva do Progresso Inteligente', () => {
  it('aplica os padrões quando a configuração está ausente ou parcial', () => {
    expect(resolveSmartProgress(undefined)).toEqual({ enabled: false, intensity: 'medio' })
    expect(resolveSmartProgress({ enabled: true } as never)).toEqual({ enabled: true, intensity: 'medio' })
    expect(resolveSmartProgress({ enabled: true, intensity: 'invalida' } as never)).toEqual({
      enabled: true,
      intensity: 'medio',
    })
  })

  it('desligado, a fração é linear ao tempo real', () => {
    expect(toVisualFraction(30, 120, { enabled: false, intensity: 'forte' })).toBeCloseTo(0.25)
    expect(toVisualFraction(30, 120, undefined)).toBeCloseTo(0.25)
  })

  it('começa em 0 e termina exatamente em 1 em todas as intensidades', () => {
    for (const i of ['suave', 'medio', 'forte'] as const) {
      expect(toVisualFraction(0, 200, on(i))).toBe(0)
      expect(toVisualFraction(200, 200, on(i))).toBe(1)
    }
  })

  it('na metade do vídeo mostra mais de 50%, crescendo com a intensidade', () => {
    const suave = toVisualFraction(50, 100, on('suave'))
    const medio = toVisualFraction(50, 100, on('medio'))
    const forte = toVisualFraction(50, 100, on('forte'))
    expect(suave).toBeCloseTo(1 - Math.pow(0.5, 1.5))
    expect(medio).toBeCloseTo(0.75)
    expect(forte).toBeCloseTo(0.875)
    expect(suave).toBeGreaterThan(0.5)
    expect(medio).toBeGreaterThan(suave)
    expect(forte).toBeGreaterThan(medio)
  })

  it('é monotônica: a barra nunca volta enquanto o vídeo avança', () => {
    for (const i of ['suave', 'medio', 'forte'] as const) {
      let prev = -1
      for (let t = 0; t <= 600; t += 0.5) {
        const v = toVisualFraction(t, 600, on(i))
        expect(v).toBeGreaterThanOrEqual(prev)
        prev = v
      }
    }
  })

  it('protege contra duração inválida e tempo fora do intervalo', () => {
    expect(toVisualFraction(30, 0, on('medio'))).toBeCloseTo(1 - Math.pow(0.5, 2)) // fallback 60s
    expect(toVisualFraction(30, NaN, on('medio'))).toBeCloseTo(0.75)
    expect(toVisualFraction(-10, 100, on('medio'))).toBe(0)
    expect(toVisualFraction(500, 100, on('medio'))).toBe(1)
    expect(toVisualFraction(NaN, 100, on('medio'))).toBe(0)
  })
})

describe('smartProgress - segmentos de capítulos', () => {
  const items: ChapterItem[] = [
    { id: 'a', time: '00:00', seconds: 0, title: 'Abertura' },
    { id: 'b', time: '00:50', seconds: 50, title: 'Pitch' },
  ]

  it('desligado, larguras são proporcionais ao tempo real', () => {
    const segs = mapChapterSegments(items, 100, 25, undefined)
    expect(segs.map((s) => s.widthPct)).toEqual([50, 50])
    expect(segs[0].fillPct).toBeCloseTo(50)
    expect(segs[1].fillPct).toBe(0)
    expect(segs[0].start).toBe(0)
    expect(segs[1].start).toBe(50)
  })

  it('ligado, segmentos seguem a curva e somam 100% da barra', () => {
    const segs = mapChapterSegments(items, 100, 25, on('medio'))
    expect(segs[0].widthPct).toBeCloseTo(75)
    expect(segs[1].widthPct).toBeCloseTo(25)
    expect(segs.reduce((acc, s) => acc + s.widthPct, 0)).toBeCloseTo(100)
  })

  it('ligado, o preenchimento total bate com a fração visual da barra contínua', () => {
    for (const t of [0, 10, 49, 50, 77, 100]) {
      const segs = mapChapterSegments(items, 100, t, on('forte'))
      const filled = segs.reduce((acc, s) => acc + (s.widthPct * s.fillPct) / 100, 0)
      expect(filled / 100).toBeCloseTo(toVisualFraction(t, 100, on('forte')))
    }
  })

  it('preenche 100% os segmentos já passados e 0% os futuros', () => {
    const segs = mapChapterSegments(items, 100, 60, on('suave'))
    expect(segs[0].fillPct).toBe(100)
    expect(segs[1].fillPct).toBeGreaterThan(0)
    expect(segs[1].fillPct).toBeLessThan(100)
    const early = mapChapterSegments(items, 100, 5, on('suave'))
    expect(early[1].fillPct).toBe(0)
  })
})
