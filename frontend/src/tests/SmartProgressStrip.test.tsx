import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SmartProgressStrip } from '../components/SmartProgressBar'
import type { ChaptersSettings } from '../types/video'

const chapters: ChaptersSettings = {
  enabled: true,
  items: [
    { id: 'a', time: '00:00', seconds: 0, title: 'Abertura' },
    { id: 'b', time: '00:50', seconds: 50, title: 'Pitch' },
  ],
}

describe('SmartProgressStrip - faixa estilo VTurb na borda inferior do player', () => {
  it('desligado, não renderiza nada', () => {
    const { container } = render(
      <SmartProgressStrip
        idPrefix="embed"
        currentTime={50}
        duration={100}
        settings={{ enabled: false, intensity: 'medio' }}
        primaryColor="#ef4444"
      />
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('com a barra de progresso oculta nos controles, não renderiza nada', () => {
    const { container } = render(
      <SmartProgressStrip
        idPrefix="embed"
        progressBar={false}
        currentTime={50}
        duration={100}
        settings={{ enabled: true, intensity: 'medio' }}
        primaryColor="#ef4444"
      />
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('ligado, é uma faixa colada na borda de baixo, de ponta a ponta, que não intercepta cliques', () => {
    render(
      <SmartProgressStrip
        idPrefix="embed"
        currentTime={50}
        duration={100}
        settings={{ enabled: true, intensity: 'medio' }}
        primaryColor="#ef4444"
      />
    )
    const strip = screen.getByTestId('embed-smart-progress-strip')
    expect(strip).toHaveStyle({ position: 'absolute', bottom: '0px', left: '0px', right: '0px' })
    expect(strip.style.pointerEvents).toBe('none')
  })

  it('ligado, a barra não tem trilho e o preenchimento segue a curva', () => {
    render(
      <SmartProgressStrip
        idPrefix="embed"
        currentTime={50}
        duration={100}
        settings={{ enabled: true, intensity: 'medio' }}
        primaryColor="#ef4444"
      />
    )
    const bar = screen.getByTestId('embed-smart-progress-bar')
    expect(bar.style.backgroundColor).toBe('')
    expect(bar).toHaveAttribute('aria-valuenow', '75')
    expect(screen.getByTestId('embed-smart-progress-fill')).toHaveStyle({ width: '75%' })
  })

  it('usa os test ids da prévia com o prefixo styling', () => {
    render(
      <SmartProgressStrip
        idPrefix="styling"
        currentTime={50}
        duration={100}
        settings={{ enabled: true, intensity: 'forte' }}
        primaryColor="#ef4444"
      />
    )
    expect(screen.getByTestId('styling-smart-progress-strip')).toBeInTheDocument()
    expect(screen.getByTestId('smart-progress-bar')).toHaveAttribute('aria-valuenow', '87.5')
  })

  it('com capítulos, segmentos seguem a curva dentro da faixa', () => {
    render(
      <SmartProgressStrip
        idPrefix="embed"
        chapters={chapters}
        currentTime={25}
        duration={100}
        settings={{ enabled: true, intensity: 'medio' }}
        primaryColor="#ef4444"
      />
    )
    const strip = screen.getByTestId('embed-smart-progress-strip')
    const seg0 = screen.getByTestId('embed-chapter-segment-0')
    expect(strip).toContainElement(seg0)
    const fill0 = parseFloat((seg0.firstChild as HTMLElement).style.width)
    expect(fill0).toBeCloseTo((0.4375 / 0.75) * 100, 1)
    expect((screen.getByTestId('embed-chapter-segment-1').firstChild as HTMLElement).style.width).toBe('0%')
  })

  it('na prévia com capítulos usa os test ids existentes', () => {
    render(
      <SmartProgressStrip
        idPrefix="styling"
        chapters={chapters}
        currentTime={25}
        duration={100}
        settings={{ enabled: true, intensity: 'medio' }}
        primaryColor="#ef4444"
      />
    )
    expect(screen.getByTestId('styling-chapters-progress-bar')).toBeInTheDocument()
    expect(screen.getByTestId('chapter-segment-1')).toBeInTheDocument()
  })

  it('clicar na faixa não quebra nem navega (sem handlers)', () => {
    render(
      <SmartProgressStrip
        idPrefix="embed"
        currentTime={10}
        duration={100}
        settings={{ enabled: true, intensity: 'suave' }}
        primaryColor="#ef4444"
      />
    )
    const bar = screen.getByTestId('embed-smart-progress-bar')
    fireEvent.click(bar)
    expect(bar).toHaveAttribute('aria-valuenow')
  })
})
