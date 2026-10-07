import React from 'react'
import { ShieldAlert } from 'lucide-react'

export const EmbedLoadingState: React.FC = () => (
  <div
    data-testid="embed-player-loading"
    // Só o spinner: o embed roda em sites de qualquer idioma, e texto fixo
    // aparecia em português num app em espanhol.
    role="status"
    aria-busy="true"
    style={{
      width: '100%',
      height: '100%',
      minHeight: '100vh',
      background: '#000000',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '0.85rem',
    }}
  >
    <div
      style={{
        width: '36px',
        height: '36px',
        border: '3px solid rgba(255, 255, 255, 0.12)',
        borderTopColor: '#10b981',
        borderRadius: '50%',
        animation: 'spin 0.75s linear infinite',
      }}
    />
  </div>
)

interface EmbedErrorStateProps {
  error: string | null
}

export const EmbedErrorState: React.FC<EmbedErrorStateProps> = ({ error }) => (
  <div
    data-testid="embed-player-error"
    style={{
      width: '100%',
      height: '100%',
      minHeight: '100vh',
      background: '#000000',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#ef4444',
      padding: '1.5rem',
      textAlign: 'center',
      boxSizing: 'border-box',
    }}
  >
    <ShieldAlert size={44} style={{ marginBottom: '0.5rem', opacity: 0.85 }} />
    <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: '#f8fafc', margin: '0 0 0.4rem 0' }}>
      {error || 'Vídeo não encontrado'}
    </h3>
    <p style={{ fontSize: '0.8rem', color: '#64748b', maxWidth: '340px', margin: 0 }}>
      Verifique o link de incorporação ou tente recarregar a página.
    </p>
  </div>
)

export const EmbedBlockedState: React.FC = () => (
  <div
    data-testid="domain-blocked-view"
    style={{
      width: '100%',
      height: '100%',
      minHeight: '100vh',
      background: '#000000',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#ef4444',
      padding: '2rem',
      textAlign: 'center',
      boxSizing: 'border-box',
    }}
  >
    <ShieldAlert size={56} style={{ marginBottom: '1rem' }} />
    <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', margin: '0 0 0.5rem 0' }}>
      Reprodução Não Autorizada
    </h2>
    <p style={{ fontSize: '0.9rem', color: '#94a3b8', maxWidth: '420px', lineHeight: 1.5, margin: 0 }}>
      Este vídeo possui proteção de domínio ativada e não tem autorização para ser reproduzido neste site.
    </p>
  </div>
)
