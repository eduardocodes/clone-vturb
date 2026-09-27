import React, { useState } from 'react'
import { ArrowLeft, Video as VideoIcon } from 'lucide-react'
import type { Video } from '../../types/video'
import { fetchVideo, getMediaUrl, reprocessVideo } from '../../services/api'
import { VideoProcessingBadge } from '../VideoProcessingBadge'
import { VideoDetailSidebar, type ActiveTab } from './VideoDetailSidebar'
import { VideoSettingsTab } from './VideoSettingsTab'
import { VideoStylingTab } from './VideoStylingTab'
import { VideoEmbedTab } from './VideoEmbedTab'
import { VideoMetricsTab } from './VideoMetricsTab'
import { VideoTurboTab } from './VideoTurboTab'
import { VideoSmartAutoplayTab } from './VideoSmartAutoplayTab'
import { VideoFloatingPlayerTab } from './VideoFloatingPlayerTab'
import { VideoPitchDelayTab } from './VideoPitchDelayTab'
import { VideoPixelsTab } from './VideoPixelsTab'
import { VideoSecurityTab } from './VideoSecurityTab'

interface VideoDetailViewProps {
  video: Video
  onBack: () => void
  onUpdateVideo: (updated: Video) => void
  showToast: (msg: string) => void
}


export const VideoDetailView: React.FC<VideoDetailViewProps> = ({
  video,
  onBack,
  onUpdateVideo,
  showToast,
}) => {
  const [activeTab, setActiveTab] = useState<ActiveTab>('settings')

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, width: '100%', height: '100%', minHeight: 0, overflow: 'hidden' }}>
      {/* Topo / Header da Mídia (Fixo e visível durante rolagem) */}
      <div
        data-testid="detail-header"
        style={{
          background: '#ffffff',
          borderBottom: '1px solid #e2e8f0',
          padding: '0.85rem 2.5rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
          zIndex: 80,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
          <button
            type="button"
            data-testid="back-to-videos-btn"
            onClick={onBack}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.5rem',
              background: 'transparent',
              border: 'none',
              color: '#475569',
              fontSize: '0.875rem',
              fontWeight: 700,
              cursor: 'pointer',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              padding: '0.4rem 0.6rem',
              borderRadius: '6px',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#f1f5f9')}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
          >
            <ArrowLeft size={16} />
            Voltar aos Vídeos
          </button>

          {/* Divisor vertical */}
          <div style={{ width: '1px', height: '24px', background: '#cbd5e1' }} />

          {/* Thumbnail e Título do Vídeo Ativo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
            <div
              style={{
                width: '44px',
                height: '28px',
                borderRadius: '4px',
                overflow: 'hidden',
                backgroundColor: '#1e293b',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              {video.thumbnail_url ? (
                <img
                  src={getMediaUrl(video.thumbnail_url)}
                  alt={video.title}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              ) : (
                <VideoIcon size={14} color="#94a3b8" />
              )}
            </div>
            <h2
              data-testid="detail-video-title"
              style={{
                fontSize: '1.15rem',
                fontWeight: 700,
                color: '#0f172a',
                margin: 0,
              }}
            >
              {video.title}
            </h2>
            <VideoProcessingBadge
              video={video}
              onChange={onUpdateVideo}
              fetchVideo={fetchVideo}
              onReprocess={async (v) => {
                try {
                  onUpdateVideo(await reprocessVideo(v.id))
                  showToast('Processamento reiniciado.')
                } catch (err) {
                  showToast(err instanceof Error ? err.message : 'Falha ao reprocessar o vídeo.')
                }
              }}
            />
          </div>
        </div>
      </div>

      {/* Conteúdo: Segunda Barra Lateral + Área de Trabalho Principal */}
      <div style={{ display: 'flex', flex: 1, width: '100%', minHeight: 0, overflow: 'hidden' }}>
        {/* Segunda Barra Lateral Modular (9 opções com badges e ícones) */}
        <VideoDetailSidebar
          video={video}
          activeTab={activeTab}
          onSelectTab={setActiveTab}
        />

        {/* Área Central de Conteúdo da Aba */}
        <main
          data-testid="video-detail-main-content"
          style={{
            flex: 1,
            padding: '2rem 3rem',
            height: '100%',
            overflowY: 'auto',
            background: '#f8fafc',
            minWidth: 0,
          }}
        >
          {activeTab === 'settings' && (
            <VideoSettingsTab
              video={video}
              onSave={onUpdateVideo}
              showToast={showToast}
            />
          )}

          {activeTab === 'styling' && (
            <VideoStylingTab
              video={video}
              onSave={onUpdateVideo}
              showToast={showToast}
            />
          )}

          {activeTab === 'embed' && (
            <VideoEmbedTab
              video={video}
              onSave={onUpdateVideo}
              showToast={showToast}
            />
          )}

          {activeTab === 'metrics' && (
            <VideoMetricsTab
              video={video}
              showToast={showToast}
            />
          )}

          {activeTab === 'turbo' && (
            <VideoTurboTab
              video={video}
              onSave={onUpdateVideo}
              showToast={showToast}
            />
          )}

          {activeTab === 'smart_autoplay' && (
            <VideoSmartAutoplayTab
              video={video}
              onSave={onUpdateVideo}
              showToast={showToast}
            />
          )}

          {activeTab === 'floating_player' && (
            <VideoFloatingPlayerTab
              video={video}
              onSave={onUpdateVideo}
              showToast={showToast}
            />
          )}

          {activeTab === 'pitch_delay' && (
            <VideoPitchDelayTab
              video={video}
              onSave={onUpdateVideo}
              showToast={showToast}
            />
          )}

          {activeTab === 'pixels' && (
            <VideoPixelsTab
              video={video}
              onSave={onUpdateVideo}
              showToast={showToast}
            />
          )}

          {activeTab === 'security' && (
            <VideoSecurityTab
              video={video}
              onSave={onUpdateVideo}
              showToast={showToast}
            />
          )}
        </main>
      </div>
    </div>
  )
}
