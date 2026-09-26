import React, { useState } from 'react'
import { Loader2, AlertCircle, Play } from 'lucide-react'
import type { Video } from '../../types/video'
import { createVideo } from '../../services/api'
import { uploadMedia, type UploadResult } from '../../services/directUpload'
import { VideoCreateHeader } from './VideoCreateHeader'
import { VideoSourceSection } from './VideoSourceSection'
import { ThumbnailSourceSection } from './ThumbnailSourceSection'
import { PlayerQuickSettings } from './PlayerQuickSettings'

interface VideoCreateViewProps {
  onBack: () => void
  onSuccess: (video: Video) => void
  showToast: (msg: string) => void
}

export const VideoCreateView: React.FC<VideoCreateViewProps> = ({
  onBack,
  onSuccess,
  showToast,
}) => {
  const [title, setTitle] = useState('')
  const [videoMode, setVideoMode] = useState<'upload' | 'url'>('upload')
  const [videoUrl, setVideoUrl] = useState('')
  const [videoFileName, setVideoFileName] = useState<string | null>(null)
  const [videoUploading, setVideoUploading] = useState(false)
  const [videoProgress, setVideoProgress] = useState(0)
  // Resultado do upload direto: a chave só vale enquanto a URL do formulário for a dele
  const [uploadedVideo, setUploadedVideo] = useState<UploadResult | null>(null)

  const [thumbMode, setThumbMode] = useState<'upload' | 'url'>('upload')
  const [thumbnailUrl, setThumbnailUrl] = useState('')
  const [thumbFileName, setThumbFileName] = useState<string | null>(null)
  const [thumbUploading, setThumbUploading] = useState(false)

  const [primaryColor, setPrimaryColor] = useState('#6366f1')
  const [autoplay, setAutoplay] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Auto-preenche o título se estiver vazio a partir do nome do arquivo
  const autoFillTitleFromFile = (fileName: string) => {
    if (!title.trim()) {
      const cleanName = fileName
        .replace(/\.[^/.]+$/, '')
        .replace(/[-_]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
      if (cleanName) {
        setTitle(cleanName.charAt(0).toUpperCase() + cleanName.slice(1))
      }
    }
  }

  const handleVideoUpload = async (file: File) => {
    try {
      setVideoUploading(true)
      setVideoProgress(0)
      setError(null)
      autoFillTitleFromFile(file.name)

      const res = await uploadMedia(file, 'video', { onProgress: setVideoProgress })
      setUploadedVideo(res)
      setVideoUrl(res.url)
      setVideoFileName(file.name)
      showToast('Arquivo de vídeo carregado com sucesso!')
    } catch (err: any) {
      setError(err.message || 'Erro ao fazer upload do vídeo.')
      setUploadedVideo(null)
      setVideoUrl('')
      setVideoFileName(null)
    } finally {
      setVideoUploading(false)
    }
  }

  const handleThumbUpload = async (file: File) => {
    try {
      setThumbUploading(true)
      setError(null)
      const res = await uploadMedia(file, 'thumbnail')
      setThumbnailUrl(res.url)
      setThumbFileName(file.name)
      showToast('Capa enviada com sucesso!')
    } catch (err: any) {
      setError(err.message || 'Erro ao fazer upload da capa.')
    } finally {
      setThumbUploading(false)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) {
      setError('Por favor, informe o título do vídeo.')
      return
    }
    if (!videoUrl.trim()) {
      setError('Por favor, selecione um arquivo de vídeo ou informe uma URL válida.')
      return
    }

    try {
      setSubmitting(true)
      setError(null)
      const newVideo = await createVideo({
        title: title.trim(),
        video_url: videoUrl.trim(),
        thumbnail_url: thumbnailUrl.trim() || undefined,
        ...(uploadedVideo?.storageKey && uploadedVideo.url === videoUrl.trim()
          ? { storage_key: uploadedVideo.storageKey, source_size_bytes: uploadedVideo.sizeBytes }
          : {}),
        player_settings: {
          primary_color: primaryColor,
          autoplay,
          show_controls: true,
          cta_enabled: false,
          cta_time: 0,
          cta_text: 'Comprar Agora',
          cta_link: 'https://checkout.com',
        },
      })
      onSuccess(newVideo)
    } catch (err: any) {
      setError(err.message || 'Erro ao criar o vídeo.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      data-testid="video-create-view"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        overflow: 'hidden',
        backgroundColor: '#f8fafc',
      }}
    >
      {/* Cabeçalho no padrão idêntico ao VideoDetailView */}
      <VideoCreateHeader onBack={onBack} />

      {/* Conteúdo Principal com Rolagem Independente */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '2.5rem 2rem' }}>
        <div
          style={{
            maxWidth: '850px',
            margin: '0 auto',
            background: '#ffffff',
            borderRadius: '16px',
            border: '1px solid #e2e8f0',
            padding: '2.5rem',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
          }}
        >
          <div style={{ marginBottom: '2rem' }}>
            <h2 style={{ fontSize: '1.4rem', fontWeight: 700, color: '#1e293b', margin: '0 0 0.4rem 0' }}>
              Subir e Configurar Novo Vídeo
            </h2>
            <p style={{ fontSize: '0.9rem', color: '#64748b', margin: 0 }}>
              Adicione seu vídeo para gerar seu player otimizado e ter acesso a todas as configurações avançadas.
            </p>
          </div>

          {error && (
            <div
              data-testid="create-error-banner"
              style={{
                background: '#fef2f2',
                border: '1px solid #fecaca',
                color: '#b91c1c',
                padding: '0.85rem 1.2rem',
                borderRadius: '10px',
                fontSize: '0.875rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.6rem',
                marginBottom: '1.75rem',
              }}
            >
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            {/* Título do Vídeo */}
            <div style={{ marginBottom: '1.75rem' }}>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: '#334155', marginBottom: '0.4rem' }}>
                Nome do Vídeo *
              </label>
              <input
                type="text"
                data-testid="create-video-title-input"
                placeholder="Ex: VSL Alta Conversão - Oferta Principal"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.75rem 1rem',
                  borderRadius: '10px',
                  border: '1px solid #cbd5e1',
                  fontSize: '0.95rem',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
            </div>

            {/* Arquivo ou URL do Vídeo */}
            <VideoSourceSection
              videoMode={videoMode}
              setVideoMode={setVideoMode}
              videoUrl={videoUrl}
              setVideoUrl={setVideoUrl}
              videoFileName={videoFileName}
              videoUploading={videoUploading}
              videoProgress={videoProgress}
              onUploadFile={handleVideoUpload}
            />

            {/* Thumbnail / Imagem de Capa */}
            <ThumbnailSourceSection
              thumbMode={thumbMode}
              setThumbMode={setThumbMode}
              thumbnailUrl={thumbnailUrl}
              setThumbnailUrl={setThumbnailUrl}
              thumbFileName={thumbFileName}
              thumbUploading={thumbUploading}
              onUploadFile={handleThumbUpload}
            />

            {/* Configurações Rápidas Iniciais do Player */}
            <PlayerQuickSettings
              primaryColor={primaryColor}
              setPrimaryColor={setPrimaryColor}
              autoplay={autoplay}
              setAutoplay={setAutoplay}
            />

            {/* Botões de Ação */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem', borderTop: '1px solid #f1f5f9', paddingTop: '1.5rem' }}>
              <button
                type="button"
                data-testid="create-video-cancel-btn"
                onClick={onBack}
                style={{
                  padding: '0.75rem 1.6rem',
                  borderRadius: '10px',
                  border: '1px solid #cbd5e1',
                  backgroundColor: '#ffffff',
                  color: '#475569',
                  fontWeight: 600,
                  fontSize: '0.95rem',
                  cursor: 'pointer',
                }}
              >
                Cancelar
              </button>

              <button
                type="submit"
                data-testid="create-video-submit-btn"
                disabled={submitting || videoUploading}
                style={{
                  padding: '0.75rem 2rem',
                  borderRadius: '10px',
                  border: 'none',
                  backgroundColor: submitting || videoUploading ? '#94a3b8' : '#ef4444',
                  color: '#ffffff',
                  fontWeight: 700,
                  fontSize: '0.95rem',
                  cursor: submitting || videoUploading ? 'not-allowed' : 'pointer',
                  boxShadow: '0 4px 12px rgba(239, 68, 68, 0.25)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  transition: 'all 0.2s ease',
                }}
              >
                {submitting ? (
                  <>
                    <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} />
                    Criando Vídeo...
                  </>
                ) : (
                  <>
                    <Play size={18} fill="#fff" />
                    Criar e Configurar Vídeo
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
