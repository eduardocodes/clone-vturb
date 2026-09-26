import { describe, it, expect } from 'vitest'
import { WatchRangeTracker } from '../utils/watchRanges'

function play(tracker: WatchRangeTracker, from: number, to: number, step = 0.25) {
  for (let t = from; t <= to + 1e-9; t += step) tracker.observe(t)
}

describe('WatchRangeTracker: trechos do vídeo realmente assistidos', () => {
  it('reprodução contínua vira um trecho só', () => {
    const tracker = new WatchRangeTracker()
    play(tracker, 0, 10)
    expect(tracker.ranges()).toEqual([[0, 10]])
  })

  it('pular para frente abre outro trecho (o que foi pulado não conta)', () => {
    const tracker = new WatchRangeTracker()
    play(tracker, 0, 5)
    play(tracker, 60, 65)
    expect(tracker.ranges()).toEqual([[0, 5], [60, 65]])
  })

  it('voltar e rever une com o que já foi visto', () => {
    const tracker = new WatchRangeTracker()
    play(tracker, 0, 10)
    play(tracker, 5, 15)
    expect(tracker.ranges()).toEqual([[0, 15]])
  })

  it('velocidade 2x continua contínua (saltos pequenos entre timeupdates)', () => {
    const tracker = new WatchRangeTracker()
    play(tracker, 0, 20, 0.5)
    expect(tracker.ranges()).toEqual([[0, 20]])
  })

  it('ignora valores inválidos', () => {
    const tracker = new WatchRangeTracker()
    tracker.observe(Number.NaN)
    tracker.observe(-3)
    play(tracker, 0, 2)
    expect(tracker.ranges()).toEqual([[0, 2]])
  })

  it('sabe se mudou desde o último envio', () => {
    const tracker = new WatchRangeTracker()
    expect(tracker.takeIfChanged()).toBeNull()
    play(tracker, 0, 3)
    expect(tracker.takeIfChanged()).toEqual([[0, 3]])
    expect(tracker.takeIfChanged()).toBeNull()
    play(tracker, 3, 4)
    expect(tracker.takeIfChanged()).toEqual([[0, 4]])
  })

  it('nunca passa de 500 trechos (limite do backend)', () => {
    const tracker = new WatchRangeTracker()
    for (let i = 0; i < 800; i++) play(tracker, i * 10, i * 10 + 1)
    expect(tracker.ranges().length).toBeLessThanOrEqual(500)
  })
})
