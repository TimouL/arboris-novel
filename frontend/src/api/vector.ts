import router from '@/router'
import { useAuthStore } from '@/stores/auth'

const API_BASE_URL = import.meta.env.MODE === 'production' ? '' : 'http://127.0.0.1:8000'
const VECTOR_PREFIX = '/api/vector'

const request = async (path: string, options: RequestInit = {}) => {
  const authStore = useAuthStore()
  const headers = new Headers({
    'Content-Type': 'application/json',
    ...options.headers
  })

  if (authStore.isAuthenticated && authStore.token) {
    headers.set('Authorization', `Bearer ${authStore.token}`)
  }

  const response = await fetch(`${API_BASE_URL}${VECTOR_PREFIX}${path}`, {
    ...options,
    headers
  })

  if (response.status === 401) {
    authStore.logout()
    router.push('/login')
    throw new Error('会话已过期，请重新登录')
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `请求失败，状态码: ${response.status}`)
  }

  if (response.status === 204) {
    return
  }

  return response.json()
}

export interface VectorProjectSummary {
  project_id: string
  title: string
  total_chapters: number
  ingested_chapters: number
  partial_chapters: number
  missing_chapters: number
  stale_chapters: number
  last_ingested_at?: string | null
  has_vectors: boolean
}

export interface VectorProjectListResponse {
  projects: VectorProjectSummary[]
  vector_db_size_bytes?: number | null
}

export interface VectorChapterSummary {
  chapter_number: number
  title: string
  status: 'ingested' | 'partial' | 'missing' | 'stale'
  chunk_count: number
  summary_count: number
  last_ingested_at?: string | null
  confirmed: boolean
  needs_refresh: boolean
  updated_at?: string | null
  word_count?: number | null
}

export interface VectorChapterTotals {
  total: number
  ingested: number
  partial: number
  missing: number
  stale: number
}

export interface VectorChapterListResponse {
  project_id: string
  totals: VectorChapterTotals
  chapters: VectorChapterSummary[]
}

export interface VectorChunkDetail {
  chunk_index: number
  chapter_title?: string | null
  content: string
  embedding_dim: number
  metadata: Record<string, any>
  created_at?: string | null
}

export interface VectorSummaryDetail {
  title: string
  summary: string
  embedding_dim: number
  created_at?: string | null
}

export interface VectorChapterDetailResponse {
  project_id: string
  chapter_number: number
  chunks: VectorChunkDetail[]
  summary?: VectorSummaryDetail | null
}

export interface VectorOperationResult {
  processed: number
  skipped: number
  failed: number
  message?: string | null
}

export interface VectorRetrievalTestRequest {
  query: string
  top_k_chunks?: number
  top_k_summaries?: number
}

export interface VectorRetrievalChunk {
  chapter_number: number
  chunk_index?: number | null
  chapter_title?: string | null
  content: string
  score: number
}

export interface VectorRetrievalSummary {
  chapter_number: number
  title: string
  summary: string
  score: number
}

export interface VectorRetrievalTestResponse {
  query: string
  chunks: VectorRetrievalChunk[]
  summaries: VectorRetrievalSummary[]
}

export class VectorAPI {
  static getProjects(): Promise<VectorProjectListResponse> {
    return request('/projects')
  }

  static getProjectChapters(projectId: string): Promise<VectorChapterListResponse> {
    return request(`/projects/${projectId}/chapters`)
  }

  static getChapterDetail(projectId: string, chapterNumber: number): Promise<VectorChapterDetailResponse> {
    return request(`/projects/${projectId}/chapters/${chapterNumber}`)
  }

  static reingest(projectId: string, chapterNumbers: number[]): Promise<VectorOperationResult> {
    return request(`/projects/${projectId}/chapters/reingest`, {
      method: 'POST',
      body: JSON.stringify({ chapter_numbers: chapterNumbers })
    })
  }

  static delete(projectId: string, chapterNumbers: number[]): Promise<VectorOperationResult> {
    return request(`/projects/${projectId}/chapters/delete`, {
      method: 'POST',
      body: JSON.stringify({ chapter_numbers: chapterNumbers })
    })
  }

  static testRetrieval(projectId: string, payload: VectorRetrievalTestRequest): Promise<VectorRetrievalTestResponse> {
    return request(`/projects/${projectId}/retrieval-test`, {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  }
}
