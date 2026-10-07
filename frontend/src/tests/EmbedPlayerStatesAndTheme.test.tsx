import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { EmbedLoadingState, EmbedErrorState, EmbedBlockedState } from '../components/EmbedPlayerStates'

describe('EmbedPlayer States and Dark Theme Integrity', () => {
  it('renderiza o EmbedLoadingState com fundo 100% preto (#000000) e spinner de carregamento', () => {
    render(<EmbedLoadingState />)
    const el = screen.getByTestId('embed-player-loading')
    expect(el).toBeInTheDocument()
    expect(el).toHaveStyle({ background: '#000000' })
    expect(screen.getByRole('status')).toBe(el)
  })

  it('EmbedLoadingState não mostra texto: o embed roda em sites de qualquer idioma', () => {
    // "Carregando player..." aparecia em app espanhol/italiano do Shiba.
    render(<EmbedLoadingState />)
    expect(screen.getByTestId('embed-player-loading').textContent).toBe('')
  })

  it('renderiza o EmbedErrorState com fundo 100% preto (#000000) e mensagem informativa amigável', () => {
    render(<EmbedErrorState error="Vídeo indisponível ou excluído." />)
    const el = screen.getByTestId('embed-player-error')
    expect(el).toBeInTheDocument()
    expect(el).toHaveStyle({ background: '#000000' })
    expect(screen.getByText('Vídeo indisponível ou excluído.')).toBeInTheDocument()
  })

  it('renderiza o EmbedBlockedState com fundo 100% preto (#000000) e alerta de domínio não autorizado', () => {
    render(<EmbedBlockedState />)
    const el = screen.getByTestId('domain-blocked-view')
    expect(el).toBeInTheDocument()
    expect(el).toHaveStyle({ background: '#000000' })
    expect(screen.getByText('Reprodução Não Autorizada')).toBeInTheDocument()
  })
})
