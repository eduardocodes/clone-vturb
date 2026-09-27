import React, { useState, useEffect } from 'react'
import { Play, Trash2, Video as VideoIcon, Plus, Sliders } from 'lucide-react'
import type { Video } from '../types/video'
import { getMediaUrl } from '../services/api'
import { VideoPagination } from './VideoPagination'
import { VideoProcessingBadge } from './VideoProcessingBadge'

interface VideoListProps {
  videos: Video[]
  loading: boolean
  onDelete: (video: Video) => void
  onBulkDelete?: (videos: Video[]) => void
  onEdit: (video: Video) => void
  onOpenImport: () => void
  onEmbed?: (video: Video) => void
  onMetrics?: (video: Video) => void
}

export const VideoList: React.FC<VideoListProps> = ({
  videos,
  loading,
  onEmbed,
  onMetrics,
  onDelete,
  onBulkDelete,
  onEdit,
  onOpenImport,
}) => {
  const PAGE_SIZE = 20
  const [currentPage, setCurrentPage] = useState(1)
  const safeVideos = Array.isArray(videos) ? videos : []
  const [selectedIds, setSelectedIds] = useState<string[]>([])

  useEffect(() => {
    const valid = new Set(safeVideos.map((v) => v.id))
    setSelectedIds((prev) => prev.filter((id) => valid.has(id)))
  }, [safeVideos])

  const totalPages = Math.max(1, Math.ceil(safeVideos.length / PAGE_SIZE))
  const safeCurrentPage = Math.min(Math.max(1, currentPage), totalPages)
  const startIndex = (safeCurrentPage - 1) * PAGE_SIZE
  const endIndex = Math.min(startIndex + PAGE_SIZE, safeVideos.length)
  const paginatedVideos = safeVideos.slice(startIndex, endIndex)

  const allSelected = safeVideos.length > 0 && selectedIds.length === safeVideos.length
  const isIndeterminate = selectedIds.length > 0 && selectedIds.length < safeVideos.length

  const handleToggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds([])
    } else {
      setSelectedIds(safeVideos.map((v) => v.id))
    }
  }

  const handleToggleSelectVideo = (videoId: string) => {
    setSelectedIds((prev) =>
      prev.includes(videoId) ? prev.filter((id) => id !== videoId) : [...prev, videoId]
    )
  }

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr)
      if (isNaN(d.getTime())) return dateStr
      const datePart = d.toLocaleDateString('pt-BR', { timeZone: 'America/Sao_Paulo' })
      const timePart = d.toLocaleTimeString('pt-BR', {
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'America/Sao_Paulo',
      })
      return `${datePart} às ${timePart}`
    } catch {
      return dateStr
    }
  }

  if (loading) {
    return (
      <div style={{ padding: '4rem', textAlign: 'center', color: '#6b7280', fontSize: '0.95rem' }}>
        Carregando vídeos...
      </div>
    )
  }

  if (safeVideos.length === 0) {
    return (
      <div
        data-testid="empty-videos-state"
        style={{
          backgroundColor: '#ffffff',
          borderRadius: '16px',
          border: '1px solid #e5e7eb',
          padding: '5rem 2rem',
          textAlign: 'center',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
        }}
      >
        <div
          style={{
            width: '64px',
            height: '64px',
            borderRadius: '50%',
            backgroundColor: '#fee2e2',
            color: '#ef4444',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 1.25rem',
          }}
        >
          <VideoIcon size={32} />
        </div>
        <h3
          data-testid="empty-message-title"
          style={{
            fontSize: '1.25rem',
            fontWeight: 700,
            color: '#111827',
            marginBottom: '0.5rem',
          }}
        >
          Nenhum vídeo criado ainda
        </h3>
        <p style={{ color: '#6b7280', fontSize: '0.9rem', maxWidth: '420px', margin: '0 auto 1.5rem', lineHeight: '1.5' }}>
          Você ainda não possui nenhum vídeo cadastrado. Importe seu primeiro vídeo para começar a gerar embeds e analisar suas métricas.
        </p>
        <button
          type="button"
          data-testid="empty-create-btn"
          onClick={onOpenImport}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.4rem',
            padding: '0.65rem 1.4rem',
            borderRadius: '8px',
            border: 'none',
            backgroundColor: '#ef4444',
            color: '#ffffff',
            fontWeight: 600,
            fontSize: '0.9rem',
            cursor: 'pointer',
            boxShadow: '0 2px 6px rgba(239, 68, 68, 0.25)',
          }}
        >
          <Plus size={16} />
          Criar Primeiro Vídeo
        </button>
      </div>
    )
  }

  return (
    <div
      data-testid="videos-table-container"
      style={{
        backgroundColor: '#ffffff',
        borderRadius: '12px',
        border: '1px solid #e5e7eb',
        overflow: 'hidden',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
      }}
    >
      {/* Barra de Seleção / Cabeçalho da Tabela */}
      <div
        data-testid="selection-header-bar"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0.85rem 1.5rem',
          backgroundColor: selectedIds.length > 0 ? '#fef2f2' : '#f8fafc',
          borderBottom: '1px solid #e2e8f0',
          transition: 'background-color 0.15s ease',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <input
            type="checkbox"
            data-testid="select-all-checkbox"
            checked={allSelected}
            ref={(el) => {
              if (el) el.indeterminate = isIndeterminate
            }}
            onChange={handleToggleSelectAll}
            style={{
              width: '18px',
              height: '18px',
              borderRadius: '4px',
              border: '1px solid #cbd5e1',
              cursor: 'pointer',
              accentColor: '#ef4444',
            }}
          />
          <span
            data-testid="select-all-label"
            onClick={handleToggleSelectAll}
            style={{
              fontSize: '0.875rem',
              fontWeight: 600,
              color: selectedIds.length > 0 ? '#991b1b' : '#64748b',
              cursor: 'pointer',
              userSelect: 'none',
            }}
          >
            {selectedIds.length > 0
              ? `${selectedIds.length} ${selectedIds.length === 1 ? 'vídeo selecionado' : 'vídeos selecionados'}`
              : 'Selecionar todos'}
          </span>
        </div>

        {selectedIds.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <button
              type="button"
              data-testid="clear-selection-btn"
              onClick={() => setSelectedIds([])}
              style={{
                fontSize: '0.8rem',
                color: '#64748b',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                textDecoration: 'underline',
              }}
            >
              Desmarcar todos
            </button>

            <button
              type="button"
              data-testid="bulk-delete-btn"
              onClick={() => {
                const toDelete = videos.filter((v) => selectedIds.includes(v.id))
                onBulkDelete?.(toDelete)
              }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.4rem',
                padding: '0.45rem 0.9rem',
                borderRadius: '8px',
                border: 'none',
                backgroundColor: '#ef4444',
                color: '#ffffff',
                fontSize: '0.85rem',
                fontWeight: 600,
                cursor: 'pointer',
                boxShadow: '0 2px 5px rgba(239, 68, 68, 0.25)',
                transition: 'all 0.15s ease',
              }}
            >
              <Trash2 size={15} />
              <span>Excluir selecionados ({selectedIds.length})</span>
            </button>
          </div>
        )}
      </div>

      {paginatedVideos.map((video) => (
        <div
          key={video.id}
          data-testid={`video-row-${video.id}`}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '1rem 1.5rem',
            borderBottom: '1px solid #f1f5f9',
            backgroundColor: selectedIds.includes(video.id) ? '#fff8f8' : 'transparent',
            transition: 'background-color 0.15s ease',
          }}
          onMouseEnter={(e) => {
            if (!selectedIds.includes(video.id)) e.currentTarget.style.backgroundColor = '#f8fafc'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = selectedIds.includes(video.id) ? '#fff8f8' : 'transparent'
          }}
        >
          {/* Lado Esquerdo: Checkbox, Thumbnail e Título */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', flex: 1 }}>
            <input
              type="checkbox"
              data-testid={`video-checkbox-${video.id}`}
              checked={selectedIds.includes(video.id)}
              onChange={() => handleToggleSelectVideo(video.id)}
              style={{
                width: '18px',
                height: '18px',
                borderRadius: '4px',
                border: '1px solid #cbd5e1',
                cursor: 'pointer',
                accentColor: '#ef4444',
              }}
            />

            {/* Thumbnail com mini play */}
            <div
              style={{
                position: 'relative',
                width: '64px',
                height: '42px',
                borderRadius: '6px',
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
                <div style={{ width: '100%', height: '100%', backgroundColor: '#334155' }} />
              )}
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  backgroundColor: 'rgba(0, 0, 0, 0.35)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Play size={14} color="#ffffff" fill="#ffffff" />
              </div>
            </div>

            {/* Título do Vídeo */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span
                data-testid={`video-title-${video.id}`}
                onClick={() => onEdit(video)}
                style={{
                  fontSize: '0.95rem',
                  fontWeight: 600,
                  color: '#1e293b',
                  cursor: 'pointer',
                }}
                title="Clique para abrir as configurações e métricas do vídeo"
              >
                {video.title}
              </span>
              <VideoProcessingBadge video={video} />
            </div>
          </div>

          {/* Lado Direito: Data e Hora, Plays e Botão Único de Edição */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.75rem' }}>
            {/* Data e Hora de Upload (Horário de Brasília) */}
            <span
              data-testid={`video-created-at-${video.id}`}
              style={{ color: '#64748b', fontSize: '0.85rem', whiteSpace: 'nowrap', fontWeight: 500 }}
              title="Data e hora de envio (Horário de Brasília)"
            >
              {formatDate(video.created_at)}
            </span>

            {/* Contador de Plays / Views Real */}
            <span
              data-testid={`video-plays-${video.id}`}
              style={{
                color: '#334155',
                fontSize: '0.9rem',
                fontWeight: 600,
                minWidth: '35px',
                textAlign: 'right',
              }}
              title={`${video.plays_count || 0} reproduções`}
            >
              {video.plays_count || 0}
            </span>

            {/* Botões de Ação */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              {/* Botão Único de Edição / Gerenciamento */}
              <button
                type="button"
                data-testid={`edit-btn-${video.id}`}
                onClick={() => onEdit(video)}
                title="Editar Configurações, Embedding e Métricas"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.45rem',
                  padding: '0.45rem 1rem',
                  borderRadius: '8px',
                  border: '1px solid #cbd5e1',
                  backgroundColor: '#ffffff',
                  color: '#1e293b',
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  boxShadow: '0 1px 2px rgba(0, 0, 0, 0.05)',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = '#f8fafc'
                  e.currentTarget.style.borderColor = '#94a3b8'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = '#ffffff'
                  e.currentTarget.style.borderColor = '#cbd5e1'
                }}
              >
                <Sliders size={14} color="#4f46e5" />
                <span>Editar</span>
              </button>

              {/* Excluir */}
              <button
                type="button"
                data-testid={`delete-btn-${video.id}`}
                onClick={() => onDelete(video)}
                title="Excluir Vídeo"
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#ef4444',
                  cursor: 'pointer',
                  padding: '0.45rem',
                  borderRadius: '6px',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                <Trash2 size={18} />
              </button>
            </div>
          </div>
        </div>
      ))}

      {/* Barra de Paginação Modular */}
      <VideoPagination
        currentPage={safeCurrentPage}
        totalPages={totalPages}
        totalVideos={videos.length}
        startIndex={startIndex}
        endIndex={endIndex}
        onPageChange={(page) => setCurrentPage(page)}
      />
    </div>
  )
}
