import { defineStore } from 'pinia'
import { ref } from 'vue'
import { NovelAPI, type AIDetectionResponse } from '@/api/novel'

type DetectionStatus = 'idle' | 'running' | 'success' | 'error'

export interface DetectionState extends AIDetectionResponse {
  status: DetectionStatus
  error_message?: string
  updatedAt?: number
  content_hash?: string
}

const defaultState: DetectionState = {
  status: 'idle',
  confidence: undefined,
  available_uses: undefined,
  segments: [],
  text_hash: undefined,
  error_message: undefined,
  updatedAt: undefined,
  content_hash: undefined
}

export const useAIDetectionStore = defineStore('ai-detection', () => {
  const detections = ref<Record<string, DetectionState>>({})

  const keyOf = (projectId: string, chapterNumber: number) => `${projectId}:${chapterNumber}`

  function getState(projectId: string, chapterNumber: number): DetectionState {
    const key = keyOf(projectId, chapterNumber)
    return detections.value[key] || { ...defaultState }
  }

  function setState(projectId: string, chapterNumber: number, state: DetectionState) {
    const key = keyOf(projectId, chapterNumber)
    detections.value[key] = { ...state, updatedAt: Date.now() }
  }

  function invalidate(projectId: string, chapterNumber: number) {
    const key = keyOf(projectId, chapterNumber)
    detections.value[key] = { ...defaultState }
  }

  async function fetchLatest(projectId: string, chapterNumber: number) {
    const result = await NovelAPI.getLatestAIDetection(projectId, chapterNumber)
    setState(projectId, chapterNumber, { ...result, status: result.status || 'success' })
    return getState(projectId, chapterNumber)
  }

  async function runDetection(projectId: string, chapterNumber: number, text?: string, timeoutSeconds?: number) {
    const previous = getState(projectId, chapterNumber)
    setState(projectId, chapterNumber, { ...previous, status: 'running', error_message: undefined })
    try {
      const result = await NovelAPI.detectChapterAI(projectId, chapterNumber, text, timeoutSeconds)
      setState(projectId, chapterNumber, { ...result, status: result.status || 'success', content_hash: result.content_hash })
      return getState(projectId, chapterNumber)
    } catch (error) {
      const message = error instanceof Error ? error.message : '检测失败'
      setState(projectId, chapterNumber, { ...previous, status: 'error', error_message: message })
      throw error
    }
  }

  return {
    getState,
    setState,
    runDetection,
    invalidate,
    fetchLatest,
  }
})
