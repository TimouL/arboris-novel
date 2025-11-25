<template>
  <div class="space-y-6">
    <div class="bg-green-50 border border-green-200 rounded-xl p-4 mb-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2 text-green-800">
          <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
          </svg>
          <span class="font-medium">这个章节已经完成</span>
        </div>

        <button
          v-if="selectedChapter.versions && selectedChapter.versions.length > 0"
          @click="$emit('showVersionSelector', true)"
          class="text-green-700 hover:text-green-800 text-sm font-medium flex items-center gap-1"
        >
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path d="M10 12a2 2 0 100-4 2 2 0 000 4z"></path>
            <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd"></path>
          </svg>
          查看所有版本
        </button>
      </div>
    </div>

    <div class="bg-gray-50 rounded-xl p-6">
      <div class="mb-4">
        <h4 class="font-semibold text-gray-800">章节内容</h4>
      </div>

      <div class="prose max-w-none">
        <div class="whitespace-pre-wrap text-gray-700 leading-relaxed">
          <template v-if="highlightedSegments && highlightedSegments.length">
            <template v-for="(seg, idx) in highlightedSegments" :key="idx">
              <span :class="segmentClass(seg.label)">{{ seg.text }}</span>
            </template>
          </template>
          <template v-else>
            {{ cleanContent }}
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Chapter, AIDetectionSegment } from '@/api/novel'
import type { DetectionState } from '@/stores/aiDetection'

interface Props {
  selectedChapter: Chapter
  detectionState?: DetectionState
}

const props = defineProps<Props>()
const selectedChapter = computed(() => props.selectedChapter)
const cleanContent = computed(() => cleanVersionContent(selectedChapter.value.content || ''))
type HighlightSegment = { text: string; label: number | null }

const hashString = (value: string): string => {
  let hash = 0
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0
  }
  return hash.toString(16)
}

const detectionUsable = computed(() => {
  const state = props.detectionState
  if (!state || state.status !== 'success') return false
  const contentHash = hashString(cleanContent.value)
  if (state.content_hash && state.content_hash !== contentHash) return false
  return true
})

const highlightedSegments = computed<HighlightSegment[] | null>(() => {
  const state = props.detectionState
  if (!detectionUsable.value || !state || !state.segments?.length) return null
  const content = cleanContent.value
  if (!content) return null
  return buildSegments(content, state.segments)
})

defineEmits(['showVersionSelector'])

const cleanVersionContent = (content: string): string => {
  if (!content) return ''
  try {
    const parsed = JSON.parse(content)
    if (parsed && typeof parsed === 'object' && parsed.content) {
      content = parsed.content
    }
  } catch (error) {
    // not a json
  }
  let cleaned = content.replace(/^"|"$/g, '')
  cleaned = cleaned.replace(/\\n/g, '\n')
  cleaned = cleaned.replace(/\\"/g, '"')
  cleaned = cleaned.replace(/\\t/g, '\t')
  cleaned = cleaned.replace(/\\\\/g, '\\')
  return cleaned
}


const buildSegments = (content: string, segments: AIDetectionSegment[]): HighlightSegment[] | null => {
  const parts: HighlightSegment[] = []
  let cursor = 0

  for (const seg of segments) {
    const text = seg.text || ''
    if (!text) continue
    const idx = content.indexOf(text, cursor)
    if (idx === -1) {
      return null
    }
    if (idx > cursor) {
      parts.push({ text: content.slice(cursor, idx), label: null })
    }
    parts.push({ text, label: seg.label })
    cursor = idx + text.length
  }

  if (cursor < content.length) {
    parts.push({ text: content.slice(cursor), label: null })
  }

  return parts
}

const segmentClass = (label: number | null) => {
  if (label === 1) return 'bg-red-100'
  if (label === 2) return 'bg-amber-100'
  if (label === 0) return 'bg-emerald-100'
  return ''
}
</script>
