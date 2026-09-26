import React from 'react'
import { Smartphone, Laptop, Globe, Compass, Share2 } from 'lucide-react'

export type BreakdownTab = 'countries' | 'devices' | 'os' | 'browsers' | 'traffic'

interface VTurbMetricsBreakdownProps {
  tab: BreakdownTab
}

const PANELS: Record<BreakdownTab, { title: string; icon: React.ComponentType<{ size?: number; color?: string }> }> = {
  devices: { title: 'Distribuição por Dispositivo', icon: Smartphone },
  countries: { title: 'Acessos por País', icon: Globe },
  os: { title: 'Sistemas Operacionais', icon: Laptop },
  browsers: { title: 'Navegadores', icon: Compass },
  traffic: { title: 'Origem do Tráfego', icon: Share2 },
}

/**
 * Painéis de detalhamento. O player ainda não coleta país, dispositivo, sistema,
 * navegador nem origem: o painel diz isso em vez de mostrar números de exemplo.
 */
export const VTurbMetricsBreakdown: React.FC<VTurbMetricsBreakdownProps> = ({ tab }) => {
  const { title, icon: Icon } = PANELS[tab]
  return (
    <div
      data-testid={`vturb-panel-${tab}`}
      style={{
        background: '#000000',
        borderRadius: '10px',
        padding: '1.75rem',
        border: '1px solid rgba(255,255,255,0.08)',
      }}
    >
      <h5 style={{ margin: '0 0 0.75rem', fontSize: '0.95rem', color: '#f8fafc', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <Icon size={16} color="#38bdf8" /> {title}
      </h5>
      <p data-testid={`vturb-panel-${tab}-empty`} style={{ margin: 0, fontSize: '0.85rem', color: '#94a3b8' }}>
        Ainda não coletamos essa informação no player. Por enquanto, use as abas de retenção e de horário.
      </p>
    </div>
  )
}
