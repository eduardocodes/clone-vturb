import { describe, it, expect } from 'vitest'
import { curveRetentionAt, generateCurvePaths } from '../components/video-detail/metrics/retentionChartHelpers'

const curve = { bucket_seconds: 1, sessions: 10, values: [1, 0.9, 0.8, 0.5, 0.5] }

describe('curva de retenção por segundo no gráfico', () => {
  it('lê a retenção no ponto do cursor, no tempo do vídeo', () => {
    expect(curveRetentionAt(curve, 0, 4)).toBeCloseTo(100)
    expect(curveRetentionAt(curve, 100, 4)).toBeCloseTo(50)
    expect(curveRetentionAt(curve, 50, 4)).toBeCloseTo(80)
  })

  it('depois do último segundo assistido a retenção é zero', () => {
    // vídeo de 100 s, ninguém passou dos 5 s
    expect(curveRetentionAt(curve, 50, 100)).toBe(0)
  })

  it('o eixo X é o tempo do vídeo: a curva ocupa só o trecho que tem dado', () => {
    const { retentionPathD } = generateCurvePaths(curve, 100)
    expect(retentionPathD.startsWith('M 0,')).toBe(true)
    // 5 pontos em 0..4 s de um vídeo de 100 s ficam nos primeiros 4% do eixo, depois cai a zero
    expect(retentionPathD).toContain('L 40,')
    expect(retentionPathD.trim().endsWith('1000,190')).toBe(true)
  })

  it('faixas maiores que 1 s respeitam bucket_seconds', () => {
    const wide = { bucket_seconds: 10, sessions: 2, values: [1, 0.5] }
    expect(curveRetentionAt(wide, 15, 100)).toBeCloseTo(50)
  })

  it('curva vazia vira linha no chão', () => {
    expect(generateCurvePaths({ bucket_seconds: 1, sessions: 0, values: [] }, 100).retentionPathD).toBe('M 0,190 L 1000,190')
    expect(curveRetentionAt({ bucket_seconds: 1, sessions: 0, values: [] }, 50, 100)).toBe(0)
  })
})
