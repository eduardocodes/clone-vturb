import React, { useState } from 'react'
import { Save, Film, Palette, MousePointerClick, RefreshCw } from 'lucide-react'
import type { Video } from '../../types/video'
import { updateVideo } from '../../services/api'
import { uploadMedia, type UploadResult } from '../../services/directUpload'
import { MediaSettingsSection, PlayerCustomizationSection, CtaSettingsSection } from './settings'

interface VideoSettingsTabProps {
  video: Video
  onSave: (updated: Video) => void
  showToast: (msg: string) => void
}

type SettingsSubTab = 'media' | 'player' | 'cta'

export const VideoSettingsTab: React.FC<VideoSettingsTabProps> = ({ video, onSave, showToast }) => {
  const [activeSubTab, setActiveSubTab] = useState<SettingsSubTab>('media')

  const [title, setTitle] = useState(video.title)
  const [videoUrl, setVideoUrl] = useState(video.video_url)
  const [thumbnailUrl, setThumbnailUrl] = useState(video.thumbnail_url || '')
  const [videoUploadMode, setVideoUploadMode] = useState<'url' | 'file'>('url')
  const [thumbUploadMode, setThumbUploadMode] = useState<'url' | 'file'>('url')

  const [primaryColor, setPrimaryColor] = useState(video.player_settings?.primary_color || '#6366f1')
  const [autoplay, setAutoplay] = useState(video.player_settings?.autoplay ?? true)
  const [showControls, setShowControls] = useState(video.player_settings?.show_controls ?? true)

  const [playShape, setPlayShape] = useState<'circle' | 'rounded' | 'square' | 'minimal'>(
    video.player_settings?.play_button_shape || 'circle'
  )
  const [playSize, setPlaySize] = useState<'small' | 'medium' | 'large'>(
    video.player_settings?.play_button_size || 'medium'
  )

  const [ctaEnabled, setCtaEnabled] = useState(video.player_settings?.cta_enabled ?? false)
  const [ctaTime, setCtaTime] = useState(video.player_settings?.cta_time ?? 60)
  const [ctaText, setCtaText] = useState(video.player_settings?.cta_text || 'Quero Comprar Agora')
  const [ctaLink, setCtaLink] = useState(video.player_settings?.cta_link || 'https://')

  const [saving, setSaving] = useState(false)
  const [uploadingVideo, setUploadingVideo] = useState(false)
  const [uploadingThumb, setUploadingThumb] = useState(false)
  const [uploadedVideo, setUploadedVideo] = useState<UploadResult | null>(null)

  const handleVideoFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      setUploadingVideo(true)
      const res = await uploadMedia(file, 'video')
      setUploadedVideo(res)
      setVideoUrl(res.url)
      showToast('Novo vídeo carregado com sucesso!')
    } catch {
      showToast('Erro ao fazer upload do vídeo.')
    } finally {
      setUploadingVideo(false)
    }
  }

  const handleThumbFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      setUploadingThumb(true)
      const res = await uploadMedia(file, 'thumbnail')
      setThumbnailUrl(res.url)
      showToast('Nova capa carregada com sucesso!')
    } catch {
      showToast('Erro ao fazer upload da capa.')
    } finally {
      setUploadingThumb(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setSaving(true)
      const updated = await updateVideo(video.id, {
        title,
        video_url: videoUrl,
        thumbnail_url: thumbnailUrl || undefined,
        ...(uploadedVideo?.storageKey && uploadedVideo.url === videoUrl
          ? { storage_key: uploadedVideo.storageKey, source_size_bytes: uploadedVideo.sizeBytes }
          : {}),
        player_settings: {
          ...video.player_settings,
          primary_color: primaryColor,
          autoplay,
          show_controls: showControls,
          cta_enabled: ctaEnabled,
          cta_time: Number(ctaTime),
          cta_text: ctaText,
          cta_link: ctaLink,
          play_button_shape: playShape,
          play_button_size: playSize,
        },
      })
      onSave(updated)
      showToast('Configurações do vídeo salvas com sucesso!')
    } catch {
      showToast('Erro ao salvar alterações.')
    } finally {
      setSaving(false)
    }
  }

  const subTabs = [
    { id: 'media' as const, label: 'Mídia & Vídeo', icon: Film, testId: 'settings-subtab-media' },
    { id: 'player' as const, label: 'Aparência do Player', icon: Palette, testId: 'settings-subtab-player' },
    { id: 'cta' as const, label: 'Botão de CTA & Pitch', icon: MousePointerClick, testId: 'settings-subtab-cta' },
  ]

  return (
    <form onSubmit={handleSubmit} style={{ maxWidth: '820px', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Barra de Sub-Abas Internas */}
      <div
        style={{
          display: 'flex',
          gap: '0.5rem',
          background: '#f1f5f9',
          padding: '0.35rem',
          borderRadius: '10px',
          border: '1px solid #e2e8f0',
        }}
      >
        {subTabs.map((tab) => {
          const Icon = tab.icon
          const isActive = activeSubTab === tab.id
          return (
            <button
              key={tab.id}
              type="button"
              data-testid={tab.testId}
              onClick={() => setActiveSubTab(tab.id)}
              style={{
                flex: 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '0.5rem',
                padding: '0.65rem 1rem',
                borderRadius: '8px',
                border: 'none',
                background: isActive ? '#ffffff' : 'transparent',
                color: isActive ? '#4f46e5' : '#64748b',
                fontWeight: isActive ? 700 : 500,
                fontSize: '0.88rem',
                cursor: 'pointer',
                boxShadow: isActive ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
                transition: 'all 0.15s ease',
              }}
            >
              <Icon size={16} color={isActive ? '#4f46e5' : '#64748b'} />
              <span>{tab.label}</span>
            </button>
          )
        })}
      </div>

      {/* Conteúdo das Sub-Abas (permanecem montadas para não perder inputs nem estado) */}
      <div style={{ display: activeSubTab === 'media' ? 'block' : 'none' }}>
        <MediaSettingsSection
          title={title}
          setTitle={setTitle}
          videoUrl={videoUrl}
          setVideoUrl={setVideoUrl}
          thumbnailUrl={thumbnailUrl}
          setThumbnailUrl={setThumbnailUrl}
          videoUploadMode={videoUploadMode}
          setVideoUploadMode={setVideoUploadMode}
          thumbUploadMode={thumbUploadMode}
          setThumbUploadMode={setThumbUploadMode}
          uploadingVideo={uploadingVideo}
          uploadingThumb={uploadingThumb}
          handleVideoFileUpload={handleVideoFileUpload}
          handleThumbFileUpload={handleThumbFileUpload}
        />
      </div>

      <div style={{ display: activeSubTab === 'player' ? 'block' : 'none' }}>
        <PlayerCustomizationSection
          primaryColor={primaryColor}
          setPrimaryColor={setPrimaryColor}
          autoplay={autoplay}
          setAutoplay={setAutoplay}
          showControls={showControls}
          setShowControls={setShowControls}
          playShape={playShape}
          setPlayShape={setPlayShape}
          playSize={playSize}
          setPlaySize={setPlaySize}
        />
      </div>

      <div style={{ display: activeSubTab === 'cta' ? 'block' : 'none' }}>
        <CtaSettingsSection
          ctaEnabled={ctaEnabled}
          setCtaEnabled={setCtaEnabled}
          ctaTime={ctaTime}
          setCtaTime={setCtaTime}
          ctaText={ctaText}
          setCtaText={setCtaText}
          ctaLink={ctaLink}
          setCtaLink={setCtaLink}
          primaryColor={primaryColor}
        />
      </div>

      {/* Botão Fixo de Salvar Configurações */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '0.5rem', borderTop: '1px solid #f1f5f9' }}>
        <button
          type="submit"
          data-testid="settings-save-btn"
          disabled={saving}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.75rem 2rem',
            borderRadius: '10px',
            border: 'none',
            background: 'linear-gradient(135deg, #4f46e5, #4338ca)',
            color: '#ffffff',
            fontSize: '0.95rem',
            fontWeight: 700,
            cursor: saving ? 'not-allowed' : 'pointer',
            boxShadow: '0 4px 12px rgba(79, 70, 229, 0.25)',
            transition: 'all 0.2s',
          }}
        >
          {saving ? <RefreshCw size={18} className="spin" /> : <Save size={18} />}
          {saving ? 'Salvando...' : 'Salvar Configurações'}
        </button>
      </div>
    </form>
  )
}
