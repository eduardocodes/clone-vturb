import React, { useState } from 'react'
import { Palette, Save } from 'lucide-react'
import type { Video, ChaptersSettings, SmartProgressSettings } from '../../types/video'
import { updateVideo } from '../../services/api'
import {
  StylingControlsPanel,
  StylingAppearancePanel,
  StylingVideoPreview,
  StylingChaptersPanel,
  StylingSmartProgressPanel,
} from './styling'
import { resolveSmartProgress } from '../../utils/smartProgress'

interface VideoStylingTabProps {
  video: Video
  onSave: (updated: Video) => void
  showToast: (msg: string) => void
}

export const VideoStylingTab: React.FC<VideoStylingTabProps> = ({ video, onSave, showToast }) => {
  const currentSettings = video.player_settings || {}
  const controlsConfig = currentSettings.controls_config || {}

  // Estados dos Controles do Player (Imagens enviadas pelo usuário)
  const [borderRadius, setBorderRadius] = useState<number>(currentSettings.border_radius ?? 0)
  const [progressBar, setProgressBar] = useState<boolean>(controlsConfig.progress_bar ?? true)
  const [videoTime, setVideoTime] = useState<boolean>(controlsConfig.video_time ?? true)
  const [rewind10s, setRewind10s] = useState<boolean>(controlsConfig.rewind_10s ?? true)
  const [forward10s, setForward10s] = useState<boolean>(controlsConfig.forward_10s ?? true)
  const [volume, setVolume] = useState<boolean>(controlsConfig.volume ?? true)
  const [fullscreen, setFullscreen] = useState<boolean>(controlsConfig.fullscreen ?? true)
  const [speedControl, setSpeedControl] = useState<boolean>(controlsConfig.speed_control ?? true)

  // Estados de Capítulos e Proporção (Modo Celular 9:16)
  const [aspectRatio, setAspectRatio] = useState<'16:9' | '9:16'>(
    (currentSettings.aspect_ratio as any) || (currentSettings.default_ratio as any) || '16:9'
  )
  const [chapters, setChapters] = useState<ChaptersSettings>(
    currentSettings.chapters || { enabled: false, items: [] }
  )
  const [smartProgress, setSmartProgress] = useState<SmartProgressSettings>(
    resolveSmartProgress(currentSettings.smart_progress)
  )

  // Estados Visuais do Player
  const [primaryColor, setPrimaryColor] = useState<string>(currentSettings.primary_color || '#6366f1')
  const [playShape, setPlayShape] = useState<'circle' | 'rounded' | 'square' | 'minimal'>(
    currentSettings.play_button_shape || 'circle'
  )
  const [playSize, setPlaySize] = useState<'small' | 'medium' | 'large'>(
    currentSettings.play_button_size || 'medium'
  )

  const [saving, setSaving] = useState<boolean>(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setSaving(true)
      const updated = await updateVideo(video.id, {
        player_settings: {
          ...currentSettings,
          primary_color: primaryColor,
          play_button_shape: playShape,
          play_button_size: playSize,
          border_radius: borderRadius,
          aspect_ratio: aspectRatio,
          default_ratio: aspectRatio,
          controls_config: {
            rewind_10s: rewind10s,
            forward_10s: forward10s,
            volume: volume,
            fullscreen: fullscreen,
            speed_control: speedControl,
            progress_bar: progressBar,
            video_time: videoTime,
          },
          chapters: chapters,
          smart_progress: smartProgress,
        },
      })
      onSave(updated)
      showToast('Estilização e controles do vídeo salvos com sucesso!')
    } catch {
      showToast('Erro ao salvar estilização do vídeo.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      data-testid="video-styling-form"
      style={{ maxWidth: '880px', display: 'flex', flexDirection: 'column', gap: '1.75rem' }}
    >
      {/* Cabeçalho da Aba */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h2
            style={{
              margin: '0 0 0.35rem 0',
              fontSize: '1.4rem',
              fontWeight: 800,
              color: '#0f172a',
              display: 'flex',
              alignItems: 'center',
              gap: '0.6rem',
            }}
          >
            <Palette size={24} color="#4f46e5" />
            Estilização do Vídeo
          </h2>
          <p style={{ margin: 0, fontSize: '0.88rem', color: '#64748b' }}>
            Melhore o visual e a interatividade dos controles do vídeo como ele aparece no seu site.
          </p>
        </div>

        <button
          type="submit"
          data-testid="save-styling-top-btn"
          disabled={saving}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.65rem 1.35rem',
            borderRadius: '10px',
            border: 'none',
            backgroundColor: '#4f46e5',
            color: '#ffffff',
            fontWeight: 700,
            fontSize: '0.9rem',
            cursor: saving ? 'not-allowed' : 'pointer',
            opacity: saving ? 0.7 : 1,
            boxShadow: '0 2px 8px rgba(79, 70, 229, 0.3)',
            transition: 'all 0.15s ease',
          }}
        >
          <Save size={16} />
          {saving ? 'Salvando...' : 'Salvar Estilização'}
        </button>
      </div>

      {/* PARTE CENTRAL: Visualização do próprio vídeo */}
      <StylingVideoPreview
        video={video}
        primaryColor={primaryColor}
        playShape={playShape}
        playSize={playSize}
        borderRadius={borderRadius}
        progressBar={progressBar}
        videoTime={videoTime}
        rewind10s={rewind10s}
        forward10s={forward10s}
        volume={volume}
        fullscreen={fullscreen}
        speedControl={speedControl}
        aspectRatio={aspectRatio}
        onAspectRatioChange={setAspectRatio}
        chapters={chapters}
        smartProgress={smartProgress}
      />

      {/* GRID INFERIOR: Coluna Esquerda (Controles + Capítulos) + Coluna Direita (Aparência & Proporção) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '1.5rem', alignItems: 'start' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <StylingControlsPanel
            borderRadius={borderRadius}
            setBorderRadius={setBorderRadius}
            progressBar={progressBar}
            setProgressBar={setProgressBar}
            videoTime={videoTime}
            setVideoTime={setVideoTime}
            rewind10s={rewind10s}
            setRewind10s={setRewind10s}
            forward10s={forward10s}
            setForward10s={setForward10s}
            volume={volume}
            setVolume={setVolume}
            fullscreen={fullscreen}
            setFullscreen={setFullscreen}
            speedControl={speedControl}
            setSpeedControl={setSpeedControl}
          />

          <StylingChaptersPanel
            chapters={chapters}
            onChange={setChapters}
            videoDuration={video.duration || 60}
          />

          <StylingSmartProgressPanel
            smartProgress={smartProgress}
            onChange={setSmartProgress}
            progressBarVisible={progressBar}
          />
        </div>

        <StylingAppearancePanel
          primaryColor={primaryColor}
          setPrimaryColor={setPrimaryColor}
          playShape={playShape}
          setPlayShape={setPlayShape}
          playSize={playSize}
          setPlaySize={setPlaySize}
          aspectRatio={aspectRatio}
          setAspectRatio={setAspectRatio}
        />
      </div>

      {/* Botão de Salvar Inferior */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '1rem', borderTop: '1px solid #e2e8f0' }}>
        <button
          type="submit"
          data-testid="save-styling-bottom-btn"
          disabled={saving}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.75rem 1.6rem',
            borderRadius: '10px',
            border: 'none',
            backgroundColor: '#4f46e5',
            color: '#ffffff',
            fontWeight: 700,
            fontSize: '0.92rem',
            cursor: saving ? 'not-allowed' : 'pointer',
            opacity: saving ? 0.7 : 1,
            boxShadow: '0 2px 8px rgba(79, 70, 229, 0.3)',
            transition: 'all 0.15s ease',
          }}
        >
          <Save size={16} />
          {saving ? 'Salvando...' : 'Salvar Alterações de Estilização'}
        </button>
      </div>
    </form>
  )
}
