import { describe, it, expect } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { EVENT_TYPES } from '../types/analytics'

const CANDIDATES = ['/contracts/analytics-events.json', resolve(__dirname, '../../../contracts/analytics-events.json')]

describe('contrato de eventos do player com o backend', () => {
  it('os tipos de evento do front são exatamente os do contrato', () => {
    const path = CANDIDATES.find((p) => existsSync(p))
    expect(path, 'contracts/analytics-events.json não encontrado').toBeTruthy()
    const contract = JSON.parse(readFileSync(path!, 'utf-8'))
    expect([...EVENT_TYPES].sort()).toEqual([...contract.event_types].sort())
  })
})
