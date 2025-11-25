<template>
  <div v-if="show" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
    <div class="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[80vh] overflow-hidden">
      <!-- 弹窗头部 -->
      <div class="flex items-center justify-between p-6 border-b border-gray-200 gap-4 flex-wrap">
        <div>
          <h3 class="text-xl font-bold text-gray-900">版本详情</h3>
          <p class="text-sm text-gray-600 mt-1">
            版本 {{ version?.label || detailVersionIndex + 1 }}
            <span class="text-gray-400">•</span>
            约 {{ Math.round(cleanVersionContent(version?.content || '').length / 100) * 100 }} 字
            <span v-if="version?.provider" class="text-gray-400">• {{ version.provider }}</span>
          </p>
        </div>
        <div class="flex items-center gap-3">
          <button
            class="inline-flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg border transition-colors duration-200"
            :class="version?.content ? 'border-indigo-200 text-indigo-600 hover:bg-indigo-50' : 'border-gray-200 text-gray-400 cursor-not-allowed'"
            :disabled="!version?.content"
            @click="copyVersionContent"
            title="复制全文"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <rect x="5" y="9" width="10" height="10" rx="2" ry="2" stroke-width="1.7" />
              <rect x="9" y="5" width="10" height="10" rx="2" ry="2" stroke-width="1.7" />
            </svg>
            复制全文
          </button>
          <button
            @click="$emit('close')"
            class="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
            </svg>
          </button>
        </div>
      </div>

      <!-- 弹窗内容 -->
      <div class="p-6 overflow-y-auto max-h-[60vh]">
        <div class="prose max-w-none">
          <div class="whitespace-pre-wrap text-gray-700 leading-relaxed">
            {{ cleanVersionContent(version?.content || '') }}
          </div>
        </div>
      </div>

      <!-- 弹窗底部操作按钮 -->
      <div class="flex items-center justify-between p-6 border-t border-gray-200 bg-gray-50">
        <div class="text-sm text-gray-500">
          <span v-if="isCurrent" class="inline-flex items-center px-2 py-1 rounded-full bg-green-100 text-green-800 font-medium">
            <svg class="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"></path>
            </svg>
            当前选中版本
          </span>
          <span v-else class="text-gray-400">未选中版本</span>
        </div>

        <div class="flex gap-3">
          <button
            @click="$emit('close')"
            class="px-4 py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-200 rounded-lg transition-colors"
          >
            关闭
          </button>
          <button
            v-if="!isCurrent"
            @click="$emit('selectVersion')"
            class="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
          >
            选择此版本
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ChapterVersion } from '@/api/novel'
import { computed } from 'vue'
import { globalAlert } from '@/composables/useAlert'

interface Props {
  show: boolean
  detailVersionIndex: number
  version: ChapterVersion | null
  isCurrent: boolean
}

const props = defineProps<Props>()

defineEmits(['close', 'selectVersion'])

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

const copyVersionContent = async () => {
  const content = cleanVersionContent(props.version?.content || '')
  if (!content) {
    globalAlert.showError('版本内容为空，无法复制。', '复制失败')
    return
  }

  const performCopy = async () => {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(content)
      return
    }
    const textarea = document.createElement('textarea')
    textarea.value = content
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    textarea.style.left = '-9999px'
    document.body.appendChild(textarea)
    textarea.focus()
    textarea.select()
    const success = document.execCommand('copy')
    document.body.removeChild(textarea)
    if (!success) {
      throw new Error('execCommand failed')
    }
  }

  try {
    await performCopy()
    globalAlert.showSuccess('版本内容已复制到剪贴板。', '复制成功')
  } catch (error) {
    globalAlert.showError('复制失败，请尝试手动复制内容。', '复制失败')
  }
}
</script>
