/**
 * Upload direto do navegador para o storage (R2/B2/S3) com URLs assinadas pelo backend.
 *
 * Vídeo: multipart em partes paralelas, com retentativa por parte e progresso real.
 * Capa: PUT único. Sem storage configurado no backend, cai para o envio antigo
 * (arquivo passando pelo backend). O arquivo nunca passa pelo backend no modo direto.
 */
import { API_BASE, authHeaders, handleAuthResponse, uploadFile } from './api'

export type UploadKind = 'video' | 'thumbnail'

export interface UploadResult {
  url: string
  /** Chave do vídeo no storage (só em upload direto de vídeo) */
  storageKey?: string
  sizeBytes?: number
}

interface UploadConfig {
  direct: boolean
  max_video_bytes: number
  max_image_bytes: number
  part_size: number
}

type InitResponse =
  | { method: 'multipart'; key: string; upload_id: string; part_size: number; part_count: number }
  | { method: 'put'; key: string; url: string; headers: Record<string, string>; public_url: string }

export interface UploadApi {
  config(): Promise<UploadConfig>
  init(body: { kind: UploadKind; filename: string; content_type: string; size: number }): Promise<InitResponse>
  signParts(body: { key: string; upload_id: string; part_numbers: number[] }): Promise<{ urls: Record<string, string> }>
  complete(body: {
    key: string
    upload_id: string
    size: number
    parts: { part_number: number; etag: string }[]
  }): Promise<{ key: string; url: string; size: number }>
  abort(body: { key: string; upload_id: string }): Promise<void>
  legacyUpload(file: File): Promise<{ filename: string; url: string }>
}

export interface UploadTransport {
  /** Envia uma parte e devolve o ETag informado pelo storage */
  putPart(url: string, blob: Blob, onProgress: (loaded: number) => void, signal?: AbortSignal): Promise<string>
  put(url: string, blob: Blob, headers: Record<string, string>, onProgress: (loaded: number) => void, signal?: AbortSignal): Promise<void>
}

export interface UploadOptions {
  onProgress?: (percent: number) => void
  signal?: AbortSignal
  concurrency?: number
  retries?: number
  api?: UploadApi
  transport?: UploadTransport
  sleep?: (ms: number) => Promise<void>
}

const SIGN_BATCH = 20
const DEFAULT_CONCURRENCY = 4
const DEFAULT_RETRIES = 3

export async function uploadMedia(file: File, kind: UploadKind, options: UploadOptions = {}): Promise<UploadResult> {
  const api = options.api ?? httpUploadApi
  const transport = options.transport ?? xhrTransport
  const report = progressReporter(file.size, options.onProgress)

  const cfg = await api.config()
  if (!cfg.direct) {
    const res = await api.legacyUpload(file)
    report.done()
    return { url: res.url }
  }

  const limit = kind === 'video' ? cfg.max_video_bytes : cfg.max_image_bytes
  if (limit && file.size > limit) {
    throw new Error(`Arquivo maior que o limite de ${Math.floor(limit / (1024 * 1024))} MB.`)
  }

  const init = await api.init({
    kind,
    filename: file.name,
    content_type: file.type || 'application/octet-stream',
    size: file.size,
  })

  if (init.method === 'put') {
    await transport.put(init.url, file, init.headers, (loaded) => report.set(0, loaded), options.signal)
    report.done()
    return { url: init.public_url }
  }

  try {
    const parts = await uploadParts(file, init, api, transport, report, options)
    const done = await api.complete({ key: init.key, upload_id: init.upload_id, size: file.size, parts })
    report.done()
    return { url: done.url, storageKey: done.key, sizeBytes: done.size }
  } catch (err) {
    // Sem abortar, as partes enviadas ficariam cobradas no bucket até o lifecycle limpar
    await api.abort({ key: init.key, upload_id: init.upload_id }).catch(() => undefined)
    throw err
  }
}

async function uploadParts(
  file: File,
  init: Extract<InitResponse, { method: 'multipart' }>,
  api: UploadApi,
  transport: UploadTransport,
  report: ReturnType<typeof progressReporter>,
  options: UploadOptions
): Promise<{ part_number: number; etag: string }[]> {
  const retries = options.retries ?? DEFAULT_RETRIES
  const sleep = options.sleep ?? ((ms: number) => new Promise<void>((r) => setTimeout(r, ms)))
  const signed = new Map<number, string>()
  const results: { part_number: number; etag: string }[] = []
  let next = 1

  const signFrom = async (start: number) => {
    const numbers: number[] = []
    for (let n = start; n <= init.part_count && numbers.length < SIGN_BATCH; n++) numbers.push(n)
    const { urls } = await api.signParts({ key: init.key, upload_id: init.upload_id, part_numbers: numbers })
    for (const [n, url] of Object.entries(urls)) signed.set(Number(n), url)
  }

  const sendPart = async (partNumber: number) => {
    const start = (partNumber - 1) * init.part_size
    const blob = file.slice(start, Math.min(start + init.part_size, file.size))

    for (let attempt = 1; ; attempt++) {
      if (options.signal?.aborted) throw new DOMException('Upload cancelado.', 'AbortError')
      if (!signed.has(partNumber)) await signFrom(partNumber)
      const url = signed.get(partNumber)!
      try {
        const etag = await transport.putPart(url, blob, (loaded) => report.set(partNumber, loaded), options.signal)
        results.push({ part_number: partNumber, etag })
        return
      } catch (err) {
        report.set(partNumber, 0)
        if (options.signal?.aborted || attempt >= retries) throw err
        // URL pode ter expirado ou sido rejeitada: assina de novo na próxima tentativa
        signed.delete(partNumber)
        await sleep(500 * 2 ** (attempt - 1))
      }
    }
  }

  const worker = async () => {
    while (next <= init.part_count) {
      const partNumber = next++
      await sendPart(partNumber)
    }
  }

  const concurrency = Math.max(1, Math.min(options.concurrency ?? DEFAULT_CONCURRENCY, init.part_count))
  await Promise.all(Array.from({ length: concurrency }, worker))
  return results
}

function progressReporter(total: number, onProgress?: (percent: number) => void) {
  const loadedByPart = new Map<number, number>()
  let last = -1
  const emit = (percent: number) => {
    // Nunca volta para trás (retentativa zera a parte, mas a barra não recua)
    if (percent > last) {
      last = percent
      onProgress?.(percent)
    }
  }
  return {
    set(part: number, loaded: number) {
      loadedByPart.set(part, loaded)
      const sum = [...loadedByPart.values()].reduce((a, b) => a + b, 0)
      // 99% no máximo até o storage confirmar a montagem do arquivo
      emit(Math.min(99, Math.floor((sum / Math.max(total, 1)) * 100)))
    },
    done() {
      emit(100)
    },
  }
}

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  handleAuthResponse(res)
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || 'Falha no upload.')
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

export const httpUploadApi: UploadApi = {
  config: () => postJson('/uploads/config'),
  init: (body) => postJson('/uploads/init', body),
  signParts: (body) => postJson('/uploads/sign-parts', body),
  complete: (body) => postJson('/uploads/complete', body),
  abort: (body) => postJson('/uploads/abort', body),
  legacyUpload: (file) => uploadFile(file),
}

function xhrPut(
  url: string,
  blob: Blob,
  headers: Record<string, string>,
  onProgress: (loaded: number) => void,
  signal?: AbortSignal
): Promise<XMLHttpRequest> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('PUT', url)
    for (const [name, value] of Object.entries(headers)) xhr.setRequestHeader(name, value)
    xhr.upload.onprogress = (e) => onProgress(e.loaded)
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve(xhr) : reject(new Error(`Storage respondeu ${xhr.status}.`)))
    xhr.onerror = () => reject(new Error('Falha de rede ao enviar para o storage.'))
    xhr.onabort = () => reject(new DOMException('Upload cancelado.', 'AbortError'))
    signal?.addEventListener('abort', () => xhr.abort(), { once: true })
    xhr.send(blob)
  })
}

export const xhrTransport: UploadTransport = {
  async putPart(url, blob, onProgress, signal) {
    const xhr = await xhrPut(url, blob, {}, onProgress, signal)
    const etag = xhr.getResponseHeader('ETag')
    if (!etag) {
      throw new Error('O storage não expôs o ETag. Libere "ETag" em ExposeHeaders no CORS do bucket.')
    }
    return etag
  },
  async put(url, blob, headers, onProgress, signal) {
    await xhrPut(url, blob, headers, onProgress, signal)
  },
}
