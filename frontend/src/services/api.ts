import type { Video, VideoMetrics, PlayerSettings } from '../types/video'
import type { AnalyticsEventType, WatchRangesPayload } from '../types/analytics'
import type {
  LoginResponse,
  User,
  UserInvite,
  CreateInvitePayload,
  InviteValidation,
  RegisterInvitePayload,
  SendVerificationCodePayload,
  BulkDeleteResponse,
} from '../types/auth'
import { getApiBaseUrl, API_BASE } from './apiConfig'
export { getApiBaseUrl, API_BASE }

const TOKEN_KEY = 'vturb_access_token'

export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setAuthToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function removeAuthToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export function authHeaders(): Record<string, string> {
  const token = getAuthToken()
  if (!token) return {}
  return { Authorization: `Bearer ${token}` }
}

export function handleAuthResponse(res: Response): void {
  if (res.status === 401) {
    removeAuthToken()
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('auth:session_expired'))
    }
  }
}

export async function loginApi(credentials: { email: string; password: string }): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  })
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}))
    throw new Error(errorData.detail || 'Falha ao autenticar.')
  }
  const data: LoginResponse = await res.json()
  setAuthToken(data.access_token)
  return data
}

export async function getCurrentUserApi(): Promise<User> {
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: {
      ...authHeaders(),
    },
  })
  handleAuthResponse(res)
  if (!res.ok) {
    throw new Error('Sessão expirada ou não autenticado.')
  }
  return res.json()
}

export async function fetchVideos(): Promise<Video[]> {
  const res = await fetch(`${API_BASE}/videos/`, {
    headers: {
      ...authHeaders(),
    },
  })
  handleAuthResponse(res)
  if (!res.ok) throw new Error('Falha ao carregar lista de vídeos.')
  return res.json()
}

export async function fetchVideo(id: string): Promise<Video> {
  const base = getApiBaseUrl()
  const res = await fetch(`${base}/videos/${id}`)
  if (!res.ok) throw new Error('Falha ao carregar dados do vídeo.')
  return res.json()
}

export async function createVideo(data: {
  title: string
  video_url: string
  thumbnail_url?: string
  duration?: number
  player_settings?: Partial<PlayerSettings>
  /** Chave do upload direto; com ela o backend deriva a URL pública do vídeo */
  storage_key?: string
  source_size_bytes?: number
}): Promise<Video> {
  const res = await fetch(`${API_BASE}/videos/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify(data),
  })
  handleAuthResponse(res)
  if (!res.ok) throw new Error('Falha ao criar o vídeo.')
  return res.json()
}

export async function updateVideo(
  id: string,
  data: {
    title?: string
    video_url?: string
    thumbnail_url?: string
    duration?: number
    player_settings?: Partial<PlayerSettings>
    storage_key?: string
    source_size_bytes?: number
  }
): Promise<Video> {
  const res = await fetch(`${API_BASE}/videos/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify(data),
  })
  handleAuthResponse(res)
  if (!res.ok) throw new Error('Falha ao atualizar o vídeo.')
  return res.json()
}

export async function deleteVideo(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/videos/${id}`, {
    method: 'DELETE',
    headers: {
      ...authHeaders(),
    },
  })
  handleAuthResponse(res)
  if (!res.ok) throw new Error('Falha ao excluir o vídeo.')
}

export async function bulkDeleteVideos(ids: string[]): Promise<{ deleted_count: number; deleted_ids: string[] }> {
  const res = await fetch(`${API_BASE}/videos/bulk-delete`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify({ video_ids: ids }),
  })
  handleAuthResponse(res)
  if (!res.ok) throw new Error('Falha ao excluir os vídeos selecionados.')
  return res.json()
}

export async function fetchVideoMetrics(
  id: string,
  params?: {
    period?: string
    start_date?: string
    end_date?: string
  }
): Promise<VideoMetrics> {
  const query = new URLSearchParams()
  if (params?.period) query.set('period', params.period)
  if (params?.start_date) query.set('start_date', params.start_date)
  if (params?.end_date) query.set('end_date', params.end_date)

  const qs = query.toString() ? `?${query.toString()}` : ''
  const res = await fetch(`${API_BASE}/videos/${id}/metrics${qs}`, {
    headers: {
      ...authHeaders(),
    },
  })
  handleAuthResponse(res)
  if (!res.ok) throw new Error('Falha ao obter métricas do vídeo.')
  return res.json()
}

export async function sendTelemetryEvent(
  videoId: string,
  event: {
    event_type: AnalyticsEventType
    watch_time_seconds?: number
    session_id?: string
    referer?: string
  }
): Promise<void> {
  try {
    await fetch(`${API_BASE}/videos/${videoId}/events`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(event),
    })
  } catch (err) {
    console.error('Erro ao enviar telemetria:', err)
  }
}

/**
 * Trechos assistidos da sessão (curva de retenção). Usa sendBeacon com text/plain:
 * sobrevive ao fechar a aba e não dispara preflight de CORS.
 */
export function sendWatchRanges(videoId: string, payload: WatchRangesPayload): void {
  const url = `${getApiBaseUrl()}/videos/${videoId}/watch`
  const body = JSON.stringify(payload)
  try {
    if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
      if (navigator.sendBeacon(url, new Blob([body], { type: 'text/plain;charset=UTF-8' }))) return
    }
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'text/plain;charset=UTF-8' },
      body,
      keepalive: true,
    }).catch(() => undefined)
  } catch (err) {
    console.error('Erro ao enviar trechos assistidos:', err)
  }
}

export async function uploadFile(file: File): Promise<{ filename: string; url: string }> {
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${API_BASE}/videos/upload`, {
    method: 'POST',
    headers: {
      ...authHeaders(),
    },
    body: formData,
  })
  handleAuthResponse(res)

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}))
    throw new Error(errorData.detail || 'Falha ao realizar upload do arquivo.')
  }

  const data = await res.json()
  return {
    filename: data.filename,
    url: getMediaUrl(data.url),
  }
}

export function getMediaUrl(url?: string): string {
  if (!url) return ''
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('blob:') || url.startsWith('data:')) {
    // Corrige URL do Backblaze B2 quando montada erroneamente com /file/ no endpoint S3
    return url.replace(/(https?:\/\/s3\.[^/]+\.backblazeb2\.com)\/file\//, '$1/')
  }
  return `${API_BASE}${url}`
}

export async function fetchUsers(): Promise<User[]> {
  const res = await fetch(`${API_BASE}/users/`, {
    headers: { ...authHeaders() },
  })
  handleAuthResponse(res)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Falha ao carregar lista de usuários.')
  }
  return res.json()
}

export async function deleteUser(userId: string): Promise<{ detail: string }> {
  const res = await fetch(`${API_BASE}/users/${userId}`, {
    method: 'DELETE',
    headers: { ...authHeaders() },
  })
  handleAuthResponse(res)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Falha ao excluir usuário.')
  }
  return res.json()
}

export interface UpdateUserData {
  name?: string
  email?: string
  role?: string
  password?: string
}

export async function updateUser(userId: string, data: UpdateUserData): Promise<User> {
  const res = await fetch(`${API_BASE}/users/${userId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify(data),
  })
  handleAuthResponse(res)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Falha ao atualizar dados do usuário.')
  }
  return res.json()
}

export interface ResetPasswordTriggerResult {
  success: boolean
  message: string
  token: string
  reset_url: string
}

export async function triggerUserPasswordReset(userId: string): Promise<ResetPasswordTriggerResult> {
  const res = await fetch(`${API_BASE}/users/${userId}/reset-password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
  })
  handleAuthResponse(res)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Falha ao solicitar redefinição de senha.')
  }
  return res.json()
}

export interface ValidateResetTokenResult {
  valid: boolean
  email: string
  name?: string
}

export async function validateResetToken(token: string): Promise<ValidateResetTokenResult> {
  const res = await fetch(`${API_BASE}/auth/validate-reset-token?token=${encodeURIComponent(token)}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Link de redefinição de senha inválido ou expirado.')
  }
  return res.json()
}

export async function executePasswordReset(token: string, password: string): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${API_BASE}/auth/reset-password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ token, password }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Falha ao redefinir a senha.')
  }
  return res.json()
}

export async function createInvite(payload: CreateInvitePayload): Promise<UserInvite> {
  const res = await fetch(`${API_BASE}/users/invites`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify(payload),
  })
  handleAuthResponse(res)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Falha ao gerar link de convite.')
  }
  return res.json()
}

export async function fetchInvites(): Promise<UserInvite[]> {
  const res = await fetch(`${API_BASE}/users/invites`, {
    headers: { ...authHeaders() },
  })
  handleAuthResponse(res)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Falha ao carregar convites.')
  }
  return res.json()
}

export async function validateInvite(token: string): Promise<InviteValidation> {
  const res = await fetch(`${API_BASE}/auth/invite/${encodeURIComponent(token)}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Link de convite inválido ou expirado.')
  }
  return res.json()
}

export async function registerViaInvite(payload: RegisterInvitePayload): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE}/auth/register-invite`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Falha ao cadastrar usuário.')
  }
  const data: LoginResponse = await res.json()
  setAuthToken(data.access_token)
  return data
}

export async function deleteInvite(inviteId: string): Promise<{ detail: string }> {
  const res = await fetch(`${API_BASE}/users/invites/${inviteId}`, {
    method: 'DELETE',
    headers: { ...authHeaders() },
  })
  handleAuthResponse(res)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Falha ao excluir convite.')
  }
  return res.json()
}

export async function sendVerificationCode(payload: SendVerificationCodePayload): Promise<{ message: string; email: string }> {
  const res = await fetch(`${API_BASE}/auth/send-verification-code`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Falha ao enviar código de verificação.')
  }
  return res.json()
}

export async function bulkDeleteUsers(ids: string[]): Promise<BulkDeleteResponse> {
  const res = await fetch(`${API_BASE}/users/bulk-delete`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify({ ids }),
  })
  handleAuthResponse(res)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Falha ao excluir usuários selecionados.')
  }
  return res.json()
}

export async function bulkDeleteInvites(ids: string[]): Promise<BulkDeleteResponse> {
  const res = await fetch(`${API_BASE}/users/invites/bulk-delete`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify({ ids }),
  })
  handleAuthResponse(res)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Falha ao excluir convites selecionados.')
  }
  return res.json()
}





