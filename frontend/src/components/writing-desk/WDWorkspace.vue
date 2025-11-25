<template>
  <div class="flex-1 min-w-0 h-full bg-white rounded-2xl shadow-lg border border-gray-100 flex flex-col overflow-hidden shrink-0">
    <!-- 章节工作区头部 -->
    <div v-if="selectedChapterNumber" class="border-b border-gray-100 p-6 shrink-0">
      <div class="flex items-center justify-between">
        <div>
          <div class="flex items-center gap-3 mb-2 flex-wrap">
            <h2 class="text-xl font-bold text-gray-900">第{{ selectedChapterNumber }}章</h2>
            <span
              :class="[
                'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
                isChapterCompleted(selectedChapterNumber)
                  ? 'bg-green-100 text-green-800'
                  : 'bg-gray-100 text-gray-600'
              ]"
            >
              {{ isChapterCompleted(selectedChapterNumber) ? '已完成' : '未完成' }}
            </span>
            <button
              class="inline-flex items-center gap-1 px-3 py-1 text-xs font-medium rounded-full border"
              :class="[
                'border-green-200 text-green-700 bg-green-50 hover:bg-green-100',
                detectionDisabled ? 'opacity-60 cursor-not-allowed' : ''
              ]"
              :disabled="detectionDisabled"
              @click="runDetection"
            >
              <svg v-if="detectionStatus !== 'running'" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
              </svg>
              <svg v-else class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path>
              </svg>
              {{ detectionStatus === 'running' ? '检测中' : 'AI检测' }}
            </button>
            <div
              class="inline-flex items-center gap-2 px-3 py-1 text-xs font-medium rounded-full border border-gray-200 bg-white"
              :class="detectionDisabled ? 'opacity-60 cursor-not-allowed' : ''"
            >
              <span class="text-gray-600">超时(s)</span>
              <input
                v-model.number="detectionTimeout"
                type="number"
                min="1"
                max="60"
                step="1"
                class="w-16 px-2 py-1 text-xs border border-gray-300 rounded focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500 disabled:bg-gray-50 disabled:text-gray-400"
                :disabled="detectionDisabled"
              />
            </div>
            <div v-if="hasDetection" class="flex items-center gap-3 flex-wrap">
              <div class="inline-flex items-center gap-2 text-xs px-2.5 py-1 rounded-full border border-emerald-200 bg-emerald-50 text-emerald-700">
                <span>AIGC</span>
                <span>{{ detectionConfidence }}% AI</span>
              </div>
              <div class="flex items-center gap-3 min-w-[180px]" style="width: 60%; min-width: 180px; max-width: 60%;">
                <div class="flex items-center gap-2 w-full">
                  <div class="flex-1 flex flex-col gap-1">
                    <div class="flex justify-center gap-4 text-xs text-gray-700">
                      <span class="text-emerald-700">人工 {{ breakdownMap[0] }}%</span>
                      <span class="text-amber-700">疑似 {{ breakdownMap[2] }}%</span>
                      <span class="text-red-700">AI {{ breakdownMap[1] }}%</span>
                    </div>
                    <div class="h-2 rounded-full bg-gray-100 overflow-hidden flex" style="min-width: 180px; max-width: 100%;">
                      <div class="h-full bg-emerald-400" :style="{ width: breakdownMap[0] + '%' }"></div>
                      <div class="h-full bg-amber-400" :style="{ width: breakdownMap[2] + '%' }"></div>
                      <div class="h-full bg-red-400" :style="{ width: breakdownMap[1] + '%' }"></div>
                    </div>
                  </div>
                  <span class="text-[10px] text-gray-500 whitespace-nowrap">更新时间：{{ detectionUpdatedAt }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-3 flex-wrap text-gray-700 mb-1">
            <h3 class="text-lg text-gray-700 m-0">{{ selectedChapterOutline?.title || '未知标题' }}</h3>
            <div class="flex items-center gap-2 flex-wrap text-xs text-gray-700">
              <span
                v-if="currentVersionInfo"
                class="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-100"
              >
                写作模型：{{ currentVersionInfo.modelName }}
              </span>
              <span class="text-gray-600" v-if="hasChapterContent">约 {{ displayedWordCount }} 字</span>
              <button
                class="inline-flex items-center gap-1 px-3 py-1 rounded-full border text-indigo-600 border-indigo-200 hover:bg-indigo-50 transition-colors disabled:opacity-50"
                :disabled="!hasChapterContent"
                @click="copyChapterContent(selectedChapter)"
                title="复制全文"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <rect x="5" y="9" width="10" height="10" rx="2" ry="2" stroke-width="1.8" />
                  <rect x="9" y="5" width="10" height="10" rx="2" ry="2" stroke-width="1.8" />
                </svg>
                复制
              </button>
              <button
                class="inline-flex items-center gap-1 px-3 py-1 rounded-full border text-indigo-600 border-indigo-200 hover:bg-indigo-50 transition-colors disabled:opacity-50"
                :disabled="!hasChapterContent"
                @click="exportChapterAsTxt(selectedChapter)"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v16h16V4m-4 4l-4-4-4 4m4-4v12" />
                </svg>
                导出TXT
              </button>
              <button
                v-if="canShowPromptButton"
                class="inline-flex items-center gap-1 px-3 py-1 rounded-full border text-indigo-600 border-indigo-200 hover:bg-indigo-50 transition-colors disabled:opacity-50"
                :disabled="promptLoading"
                @click="openPromptPanel"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m5-3a8 8 0 11-16 0 8 8 0 0116 0z" />
                </svg>
                查看提示词
              </button>
              <button
                class="inline-flex items-center gap-1 px-3 py-1 rounded-full border transition-colors disabled:opacity-50"
                :class="formatCleanup ? 'border-emerald-200 text-emerald-700 bg-emerald-50' : 'border-gray-200 text-gray-600 hover:bg-gray-50'"
                :disabled="promptLoading"
                @click="toggleFormatCleanup"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                </svg>
                格式整理
                <span class="text-[11px] font-medium">{{ formatCleanup ? '开' : '关' }}</span>
              </button>
            </div>
          </div>
          <p class="text-sm text-gray-600">{{ selectedChapterOutline?.summary || '暂无章节描述' }}</p>
        </div>

        <div class="flex items-center gap-2">
          <button
            v-if="isChapterCompleted(selectedChapterNumber)"
            @click="openEditModal"
            class="px-4 py-2 bg-green-600 text-white hover:bg-green-700 rounded-lg transition-colors flex items-center gap-2 whitespace-nowrap"
          >
            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path d="M13.586 3.586a2 2 0 112.828 2.828l-.793.793-2.828-2.828.793-.793zM11.379 5.793L3 14.172V17h2.828l8.38-8.379-2.83-2.828z"></path>
            </svg>
            手动编辑
          </button>
          <button
            @click="confirmRegenerateChapter"
            :disabled="generatingChapter === selectedChapterNumber"
            class="px-4 py-2 bg-indigo-600 text-white hover:bg-indigo-700 rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2 whitespace-nowrap"
          >
            <svg v-if="generatingChapter === selectedChapterNumber" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
            </svg>
            <svg v-else class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
            </svg>
            {{ generatingChapter === selectedChapterNumber ? '生成中...' : '重新生成' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 章节内容展示区 -->
    <div class="relative flex-1 p-6 overflow-y-auto">
      <component
        :is="currentComponent"
        v-bind="currentComponentProps"
        @hideVersionSelector="$emit('hideVersionSelector')"
        @update:selectedVersionIndex="$emit('update:selectedVersionIndex', $event)"
        @showVersionDetail="$emit('showVersionDetail', $event)"
        @confirmVersionSelection="$emit('confirmVersionSelection')"
        @generateChapter="forwardGenerateChapter"
        @showVersionSelector="$emit('showVersionSelector')"
        @regenerateChapter="forwardRegenerateChapter"
        @evaluateChapter="$emit('evaluateChapter')"
        @showEvaluationDetail="$emit('showEvaluationDetail')"
      />
      <transition name="fade">
        <div
          v-if="props.isSavingContent"
          class="absolute inset-0 bg-white/70 backdrop-blur-sm flex flex-col items-center justify-center text-indigo-700 gap-2 rounded-xl"
        >
          <svg class="w-6 h-6 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a12 12 0 00-12 12h4z"></path>
          </svg>
          <span class="text-sm font-medium">章节内容保存中...</span>
        </div>
      </transition>
    </div>

    <!-- 编辑章节内容模态框 -->
    <div v-if="showEditModal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div class="bg-white rounded-2xl shadow-xl w-full h-full flex flex-col">
        <div class="flex items-center justify-between p-6 border-b border-gray-200">
          <h3 class="text-lg font-semibold text-gray-900">
            编辑第{{ selectedChapterNumber }}章内容
          </h3>
          <button
            @click="closeEditModal"
            class="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"></path>
            </svg>
          </button>
        </div>

        <div class="flex-1 p-6 overflow-hidden">
          <div class="flex flex-col h-full">
            <label class="block text-sm font-medium text-gray-700 mb-2">
              章节内容
            </label>
            <textarea
              v-model="editingContent"
              class="flex-1 w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 resize-none"
              placeholder="请输入章节内容..."
              :disabled="isSaving"
            ></textarea>
            <div class="text-sm text-gray-500 mt-2">
              字数统计: {{ editingContent.length }}
            </div>
          </div>
        </div>

        <div class="flex items-center justify-end gap-3 p-6 border-t border-gray-200">
          <button
            @click="closeEditModal"
            :disabled="isSaving"
            class="px-4 py-2 text-gray-700 bg-white border border-gray-300 hover:bg-gray-50 rounded-lg transition-colors disabled:opacity-50"
          >
            取消
          </button>
          <button
            @click="saveEditedContent"
            :disabled="isSaving || !editingContent.trim() || contentUnchanged"
            class="px-4 py-2 bg-indigo-600 text-white hover:bg-indigo-700 rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            <svg v-if="isSaving" class="w-4 h-4 animate-spin" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clip-rule="evenodd"></path>
            </svg>
            {{ isSaving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <transition name="fade">
      <div v-if="showPromptPanel" class="fixed inset-0 z-50 flex justify-end">
        <div class="flex-1 bg-black/30" @click="closePromptPanel"></div>
        <div class="w-full max-w-2xl h-full bg-white shadow-2xl border-l border-gray-100 flex flex-col">
          <div class="flex items-center justify-between p-4 border-b border-gray-100">
            <div>
              <h3 class="text-lg font-semibold text-gray-900">
                章节生成提示词
                <span v-if="promptSnapshot" class="ml-2 text-sm font-medium text-indigo-700">
                  总计约 {{ formatTokens(promptSnapshot.total_tokens) }} tokens
                </span>
              </h3>
              <p class="text-xs text-gray-500">按生成时的组装顺序展示系统与用户提示词</p>
            </div>
            <button class="text-gray-400 hover:text-gray-600" @click="closePromptPanel">
              <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="p-4 overflow-y-auto flex-1 space-y-4">
            <div v-if="promptLoading" class="flex items-center justify-center h-48 text-indigo-600 gap-2">
              <svg class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4l3-3-3-3v4a12 12 0 00-12 12h4z"></path>
              </svg>
              <span class="text-sm font-medium">加载提示词...</span>
            </div>

            <div v-else-if="promptError" class="bg-rose-50 border border-rose-200 text-rose-700 p-3 rounded-lg text-sm">
              <div class="flex items-center justify-between">
                <span>{{ promptError }}</span>
                <button class="text-indigo-600 text-xs font-medium" @click="openPromptPanel">重试</button>
              </div>
            </div>

            <template v-else-if="promptSnapshot">
              <div class="bg-gray-50 border border-gray-200 rounded-lg p-3">
                <div class="flex items-center justify-between text-sm text-gray-700">
                  <span class="font-medium">系统提示词</span>
                  <div class="flex items-center gap-3 text-xs text-gray-500">
                    <button
                      class="inline-flex items-center gap-1 px-2 py-1 rounded border text-indigo-600 border-indigo-200 hover:bg-indigo-50 transition-colors"
                      @click="copySystemPrompt"
                    >
                      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <rect x="5" y="9" width="10" height="10" rx="2" ry="2" stroke-width="1.6" />
                        <rect x="9" y="5" width="10" height="10" rx="2" ry="2" stroke-width="1.6" />
                      </svg>
                      复制
                    </button>
                    <span>约 {{ formatTokens(systemTokens) }} tokens</span>
                  </div>
                </div>
                <div class="relative mt-2">
                  <pre
                    class="whitespace-pre-wrap text-sm font-mono leading-relaxed bg-white border border-gray-200 rounded-lg p-3"
                    :class="isCollapsed('system') ? 'max-h-36 overflow-hidden' : ''"
                  >{{ promptSnapshot.system_prompt }}</pre>
                  <div
                    v-if="isCollapsed('system')"
                    class="absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-white via-white/80 pointer-events-none"
                  ></div>
                </div>
                <div class="flex justify-end">
                  <button class="text-xs text-indigo-600 mt-2" @click="toggleCollapse('system')">
                    {{ isCollapsed('system') ? '展开' : '收起' }}
                  </button>
                </div>
              </div>

              <div class="flex items-center justify-between text-sm text-gray-700 px-1">
                <span class="font-medium">用户提示词（按组装顺序）</span>
                <div class="flex items-center gap-3 text-xs text-gray-500">
                  <button
                    class="inline-flex items-center gap-1 px-2 py-1 rounded border text-indigo-600 border-indigo-200 hover:bg-indigo-50 transition-colors"
                    @click="copyUserPrompt"
                  >
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <rect x="5" y="9" width="10" height="10" rx="2" ry="2" stroke-width="1.6" />
                      <rect x="9" y="5" width="10" height="10" rx="2" ry="2" stroke-width="1.6" />
                    </svg>
                    复制
                  </button>
                  <span>总计约 {{ formatTokens(promptSnapshot.total_tokens) }} tokens</span>
                </div>
              </div>

              <div class="space-y-3">
                <div
                  v-for="section in promptSnapshot.sections"
                  :key="section.key"
                  class="border border-gray-200 rounded-lg p-3 bg-white shadow-sm"
                >
                  <div class="flex items-start justify-between gap-2">
                    <div>
                      <div class="text-sm font-semibold text-gray-900">{{ section.title }}</div>
                      <div class="text-xs text-gray-500">来源：{{ section.source || '未知' }}</div>
                    </div>
                    <div class="text-xs text-gray-500">约 {{ formatTokens(section.tokens) }} tokens</div>
                  </div>
                  <div class="relative mt-2">
                    <pre
                      class="whitespace-pre-wrap text-sm font-mono leading-relaxed bg-gray-50 border border-gray-100 rounded-lg p-3"
                      :class="isCollapsed(section.key) ? 'max-h-36 overflow-hidden' : ''"
                    >{{ section.content }}</pre>
                    <div
                      v-if="isCollapsed(section.key)"
                      class="absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-gray-50 via-gray-50/80 pointer-events-none"
                    ></div>
                  </div>
                  <div class="flex justify-end">
                    <button class="text-xs text-indigo-600 mt-1" @click="toggleCollapse(section.key)">
                      {{ isCollapsed(section.key) ? '展开' : '收起' }}
                    </button>
                  </div>
                </div>
              </div>
            </template>

            <div v-else class="text-sm text-gray-500">暂无提示词记录，请重新生成章节后查看。</div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from 'vue'
import { globalAlert } from '@/composables/useAlert'
import type {
  Chapter,
  ChapterOutline,
  ChapterGenerationResponse,
  ChapterVersion,
  NovelProject,
  PromptSnapshot,
  PromptSection
} from '@/api/novel'
import { NovelAPI } from '@/api/novel'
import { useAIDetectionStore, type DetectionState } from '@/stores/aiDetection'
import WorkspaceInitial from './workspace/WorkspaceInitial.vue'
import ChapterGenerating from './workspace/ChapterGenerating.vue'
import VersionSelector from './workspace/VersionSelector.vue'
import ChapterContent from './workspace/ChapterContent.vue'
import ChapterFailed from './workspace/ChapterFailed.vue'
import ChapterEmpty from './workspace/ChapterEmpty.vue'

interface VersionGroup {
  modelKey: string
  modelName: string
  provider?: string | null
  items: Array<{ version: ChapterVersion; globalIndex: number }>
}

interface Props {
  project: NovelProject | null
  selectedChapterNumber: number | null
  generatingChapter: number | null
  evaluatingChapter: number | null
  showVersionSelector: boolean
  chapterGenerationResult: ChapterGenerationResponse | null
  selectedVersionIndex: number
  availableVersions: ChapterVersion[]
  groupedVersions: VersionGroup[]
  isSelectingVersion?: boolean
  isSavingContent?: boolean
}

const props = defineProps<Props>()

const aiDetectionStore = useAIDetectionStore()
const hashString = (value: string): string => {
  let hash = 0
  for (let i = 0; i < value.length; i++) {
    hash = (hash * 31 + value.charCodeAt(i)) >>> 0
  }
  return hash.toString(16)
}

const emit = defineEmits([
  'regenerateChapter',
  'evaluateChapter',
  'hideVersionSelector',
  'update:selectedVersionIndex',
  'showVersionDetail',
  'confirmVersionSelection',
  'generateChapter',
  'showVersionSelector',
  'showEvaluationDetail',
  'fetchChapterStatus',
  'editChapter'
])

const formatCleanup = ref(true)

const confirmRegenerateChapter = async () => {
  const confirmed = await globalAlert.showConfirm('重新生成会覆盖当前章节的现有内容，确定继续吗？', '重新生成确认')
  if (confirmed) {
    emit('regenerateChapter', { formatCleanup: formatCleanup.value })
  }
}

const forwardGenerateChapter = (payload: any) => {
  if (typeof payload === 'number') {
    emit('generateChapter', { chapterNumber: payload, formatCleanup: formatCleanup.value })
    return
  }
  emit('generateChapter', { ...(payload || {}), formatCleanup: formatCleanup.value })
}

const forwardRegenerateChapter = () => {
  emit('regenerateChapter', { formatCleanup: formatCleanup.value })
}

const toggleFormatCleanup = () => {
  formatCleanup.value = !formatCleanup.value
}

const showEditModal = ref(false)
const editingContent = ref('')
const isSaving = ref(false)
const originalContent = computed(() => cleanVersionContent(selectedChapter.value?.content || ''))
const contentUnchanged = computed(() => editingContent.value.trim() === originalContent.value.trim())

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

const openEditModal = () => {
  if (selectedChapter.value?.content) {
    editingContent.value = cleanVersionContent(selectedChapter.value.content)
    showEditModal.value = true
  }
}

const closeEditModal = () => {
  showEditModal.value = false
  editingContent.value = ''
  isSaving.value = false
}

const saveEditedContent = async () => {
  if (!props.selectedChapterNumber || !editingContent.value.trim()) return
  if (contentUnchanged.value) {
    globalAlert.showError('内容未变更，无需保存。', '未修改')
    return
  }

  isSaving.value = true
  try {
    emit('editChapter', {
      chapterNumber: props.selectedChapterNumber,
      content: editingContent.value
    })
  } catch (error) {
    console.error('保存章节内容失败:', error)
  } finally {
    if (!props.isSavingContent) {
      isSaving.value = false
    }
  }
}

const detectionTimeout = ref(10)

const runDetection = async () => {
  if (!props.project || props.selectedChapterNumber === null) {
    globalAlert.showError('未找到当前章节，无法检测。', '检测失败')
    return
  }
  if (!canDetect.value) {
    globalAlert.showError('章节内容为空，无法检测。', '检测失败')
    return
  }
  const content = cleanVersionContent(selectedChapter.value?.content || '').trim()
  const minLength = 350
  const maxLength = 20000
  if (content.length < minLength || content.length >= maxLength) {
    globalAlert.showError(`AI 检测要求正文长度需在 ${minLength}~${maxLength} 字之间（含 ${minLength}，不含 ${maxLength}），当前 ${content.length} 字。`, '检测失败')
    return
  }
  if (detectionLocked.value) {
    globalAlert.showError('检测结果已存在，需对章节内容进行修改后才可再次检测。', '检测已锁定')
    return
  }
  const proceed = await globalAlert.showConfirm('检测完成后若需再次检测，请先对正文进行实质修改。确认开始检测吗？', 'AI 检测提示')
  if (!proceed) return
  try {
    const timeoutSeconds = Math.max(1, Math.min(Number(detectionTimeout.value) || 10, 60))
    detectionTimeout.value = timeoutSeconds
    await aiDetectionStore.runDetection(props.project.id, props.selectedChapterNumber, content, timeoutSeconds)
  } catch (error) {
    const msg = error instanceof Error ? error.message : '检测失败'
    globalAlert.showError(msg, '检测失败')
  }
}

const selectedChapter = computed(() => {
  if (!props.project || props.selectedChapterNumber === null) return null
  return props.project.chapters.find(ch => ch.chapter_number === props.selectedChapterNumber) || null
})

const canShowPromptButton = computed(() => {
  if (!props.project || !props.selectedChapterNumber) return false
  if (props.selectedChapterNumber === 1) return true
  const lastCompleted = props.project.chapters
    .filter(ch => ch.generation_status === 'successful')
    .reduce((max, ch) => Math.max(max, ch.chapter_number), 0)
  return lastCompleted >= props.selectedChapterNumber - 1
})

const promptSnapshot = ref<PromptSnapshot | null>(null)
const promptLoading = ref(false)
const promptError = ref<string | null>(null)
const showPromptPanel = ref(false)
const collapsedSections = ref<Record<string, boolean>>({})
const userPromptText = computed(() => {
  const snapshot = promptSnapshot.value
  if (!snapshot) return ''
  if (snapshot.prompt_input) return snapshot.prompt_input
  const sections = snapshot.sections || []
  if (!sections.length) return ''
  return sections.map(section => `[${section.title}]\n${section.content}`).join('\n\n')
})

const systemTokens = computed(() => {
  const content = promptSnapshot.value?.system_prompt || ''
  if (!content) return 0
  return Math.max(1, Math.ceil(content.length / 4))
})

const isCollapsed = (key: string) => collapsedSections.value[key] !== false
const toggleCollapse = (key: string) => {
  collapsedSections.value[key] = !isCollapsed(key)
}

const formatTokens = (tokens: number) => {
  if (!tokens || tokens <= 0) return '--'
  if (tokens >= 1000) return `${Math.round(tokens / 10) / 100}k`
  return `${tokens}`
}

const openPromptPanel = async () => {
  if (!props.project || !props.selectedChapterNumber) return
  showPromptPanel.value = true
  promptLoading.value = true
  promptError.value = null
  try {
    let data: PromptSnapshot | null = null
    try {
      data = await NovelAPI.getChapterPromptSnapshot(props.project.id, props.selectedChapterNumber)
    } catch (err) {
      try {
        data = await NovelAPI.getChapterPromptPreview(props.project.id, props.selectedChapterNumber)
      } catch (previewErr) {
        const msg = previewErr instanceof Error ? previewErr.message : '加载提示词失败'
        promptError.value = msg
        return
      }
    }
    if (data) {
      promptSnapshot.value = data
      const collapsed: Record<string, boolean> = { system: true }
      data.sections?.forEach((item: PromptSection) => {
        collapsed[item.key] = true
      })
      collapsedSections.value = collapsed
    }
  } catch (error) {
    promptError.value = error instanceof Error ? error.message : '加载提示词失败'
  } finally {
    promptLoading.value = false
  }
}

const closePromptPanel = () => {
  showPromptPanel.value = false
}

const hasChapterContent = computed(() => {
  return !!cleanVersionContent(selectedChapter.value?.content || '').trim()
})

const displayedWordCount = computed(() => {
  const len = cleanVersionContent(selectedChapter.value?.content || '').length
  if (!len) return 0
  return Math.round(len / 100) * 100
})

const sanitizeFileName = (name: string): string => {
  return name.replace(/[\\/:*?"<>|]/g, '_')
}

const exportChapterAsTxt = (chapter?: Chapter | null) => {
  if (!chapter || !hasChapterContent.value) return

  const title = chapter.title?.trim() || `第${chapter.chapter_number}章`
  const safeTitle = sanitizeFileName(title) || `chapter-${chapter.chapter_number}`
  const content = cleanVersionContent(chapter.content || '')
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${safeTitle}.txt`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

const currentVersionInfo = computed(() => {
  if (!selectedChapter.value?.content || !selectedChapter.value.versions) return null
  const target = cleanVersionContent(selectedChapter.value.content)
  const match = selectedChapter.value.versions.find(version => cleanVersionContent(version.content).trim() === target.trim())
  if (!match) return null
  const metadata = match.metadata || {}
  return {
    modelName: metadata.model_name || match.label || (metadata.source === 'addon' ? metadata.model_key : '主模型')
  }
})

const copyChapterContent = async (chapter?: Chapter | null) => {
  if (!chapter || !hasChapterContent.value) return
  const content = cleanVersionContent(chapter.content || '')

  try {
    await copyToClipboard(content)
    globalAlert.showSuccess('章节内容已复制到剪贴板。', '复制成功')
  } catch (error) {
    globalAlert.showError('复制失败，请尝试手动复制内容。', '复制失败')
  }
}

const copyToClipboard = async (text: string) => {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }

  const textarea = document.createElement('textarea')
  textarea.value = text
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

const copyText = async (text: string, emptyMessage: string, successMessage: string) => {
  if (!text) {
    globalAlert.showError(emptyMessage, '复制失败')
    return
  }
  try {
    await copyToClipboard(text)
    globalAlert.showSuccess(successMessage, '复制成功')
  } catch (error) {
    globalAlert.showError('复制失败，请尝试手动复制内容。', '复制失败')
  }
}

const copySystemPrompt = async () => {
  await copyText(promptSnapshot.value?.system_prompt || '', '系统提示词为空，无法复制。', '系统提示词已复制到剪贴板。')
}

const copyUserPrompt = async () => {
  await copyText(userPromptText.value, '暂无用户提示词，生成后再试。', '用户提示词已复制到剪贴板。')
}

const detectionState = computed<DetectionState>(() => {
  if (!props.project || props.selectedChapterNumber === null) return { status: 'idle', segments: [] }
  return aiDetectionStore.getState(props.project.id, props.selectedChapterNumber)
})

const detectionStatus = computed(() => detectionState.value.status || 'idle')
const currentContentHash = computed(() => hashString(cleanVersionContent(selectedChapter.value?.content || '')))
const hasDetection = computed(() => detectionStatus.value === 'success')
const detectionLocked = computed(() => {
  return (
    hasDetection.value &&
    !!detectionState.value.content_hash &&
    detectionState.value.content_hash === currentContentHash.value
  )
})

watch(
  () => props.isSavingContent,
  (saving) => {
    if (!showEditModal.value) return
    if (saving) {
      isSaving.value = true
      return
    }
    if (isSaving.value) {
      const saved = editingContent.value.trim() === cleanVersionContent(selectedChapter.value?.content || '').trim()
      if (saved) {
        closeEditModal()
      } else {
        isSaving.value = false
      }
    }
  }
)

const detectionConfidence = computed(() => {
  const val = detectionState.value.confidence
  if (val === undefined || val === null) return '--'
  return Math.round(val * 10000) / 100
})
const detectionAvailable = computed(() => detectionState.value.available_uses ?? '--')
const detectionUpdatedAt = computed(() => {
  if (!detectionState.value.updatedAt) return '--'
  const date = new Date(detectionState.value.updatedAt)
  return date.toLocaleTimeString('zh-CN', { hour12: false })
})

const labelText = (label: number | null) => {
  if (label === 1) return 'AI 内容'
  if (label === 2) return '疑似 AI'
  if (label === 0) return '人工'
  return '未标注'
}

const labelTextClass = (label: number | null) => {
  if (label === 1) return 'text-red-700'
  if (label === 2) return 'text-amber-700'
  if (label === 0) return 'text-emerald-700'
  return 'text-gray-600'
}

const barClass = (label: number | null) => {
  if (label === 1) return 'bg-red-400'
  if (label === 2) return 'bg-amber-400'
  if (label === 0) return 'bg-emerald-400'
  return 'bg-gray-300'
}

const breakdownMap = computed<Record<number, number>>(() => {
  const segments = detectionState.value.segments || []
  const totalLength = segments.reduce((sum, seg) => sum + (seg.text?.length || 0), 0)
  const counts: Record<number, number> = { 0: 0, 1: 0, 2: 0 }
  for (const seg of segments) {
    const len = seg.text?.length || 0
    counts[seg.label] = (counts[seg.label] || 0) + len
  }
  const denom = totalLength || segments.length || 1
  const toPercent = (v: number) => Math.round((v / denom) * 10000) / 100
  return {
    0: toPercent(counts[0]),
    2: toPercent(counts[2]),
    1: toPercent(counts[1])
  }
})

const statusLabel = computed(() => {
  switch (detectionStatus.value) {
    case 'running':
      return '检测中'
    case 'success':
      return '检测完成'
    case 'error':
      return '检测失败'
    default:
      return '未检测'
  }
})

const canDetect = computed(() => {
  if (!props.project || props.selectedChapterNumber === null) return false
  const chapter = selectedChapter.value
  return !!(chapter && cleanVersionContent(chapter.content || '').trim())
})

const detectionDisabled = computed(() => !canDetect.value || detectionStatus.value === 'running' || detectionLocked.value)

const selectedChapterOutline = computed(() => {
  if (!props.project?.blueprint?.chapter_outline || props.selectedChapterNumber === null) return null
  return props.project.blueprint.chapter_outline.find(ch => ch.chapter_number === props.selectedChapterNumber) || null
})

const isChapterCompleted = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'successful'
}

const isChapterGenerating = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'generating'
}

const isChapterFailed = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'failed'
}

const isChapterEvaluationFailed = (chapterNumber: number) => {
  if (!props.project?.chapters) return false
  const chapter = props.project.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'evaluation_failed'
}

const canGenerateChapter = (chapterNumber: number | null) => {
  if (chapterNumber === null || !props.project?.blueprint?.chapter_outline) return false

  const outlines = props.project.blueprint.chapter_outline.sort((a, b) => a.chapter_number - b.chapter_number)

  for (const outline of outlines) {
    if (outline.chapter_number >= chapterNumber) break

    const chapter = props.project?.chapters.find(ch => ch.chapter_number === outline.chapter_number)
    if (!chapter || chapter.generation_status !== 'successful') {
      return false
    }
  }

  const currentChapter = props.project?.chapters.find(ch => ch.chapter_number === chapterNumber)
  if (currentChapter && currentChapter.generation_status === 'successful') {
    return true
  }

  return true
}

const currentComponent = computed(() => {
  if (!props.selectedChapterNumber) {
    return WorkspaceInitial
  }

  const status = selectedChapter.value?.generation_status
  if (status === 'generating' || status === 'evaluating' || status === 'selecting') {
    return ChapterGenerating
  }

  if (status === 'waiting_for_confirm' || status === 'evaluation_failed') {
    return VersionSelector
  }

  if (selectedChapter.value?.content) {
    return ChapterContent
  }
  if (isChapterFailed(props.selectedChapterNumber)) {
    return ChapterFailed
  }
  return ChapterEmpty
})

const pollingTimer = ref<number | null>(null)

const startPolling = () => {
  stopPolling()
  pollingTimer.value = window.setInterval(() => {
    emit('fetchChapterStatus')
  }, 10000)
}

const stopPolling = () => {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }
}

watch(
  () => [selectedChapter.value?.generation_status, props.evaluatingChapter, props.isSelectingVersion, props.selectedChapterNumber],
  ([status, evaluating, selecting, chapterNumber]) => {
    if (chapterNumber === null) {
      stopPolling()
      return
    }

    const needsPolling = status === 'generating' || status === 'evaluating' || status === 'selecting'

    if (needsPolling) {
      startPolling()
    } else {
      stopPolling()
    }
  },
  { immediate: true }
)

const loadDetection = async () => {
  if (!props.project || props.selectedChapterNumber === null) return
  if (!selectedChapter.value?.content) return
  try {
    await aiDetectionStore.fetchLatest(props.project.id, props.selectedChapterNumber)
  } catch (_) {
    /* ignore missing cache */
  }
}

watch(
  () => props.selectedChapterNumber,
  () => {
    void loadDetection()
  },
  { immediate: true }
)

watch(
  () => selectedChapter.value?.content,
  () => {
    void loadDetection()
  }
)

onUnmounted(() => {
  stopPolling()
})

const currentComponentProps = computed(() => {
  if (!props.selectedChapterNumber) {
    return {}
  }
  const status = selectedChapter.value?.generation_status
  if (status === 'generating' || status === 'evaluating' || status === 'selecting') {
    return {
      chapterNumber: props.selectedChapterNumber,
      status: status
    }
  }

  if (status === 'waiting_for_confirm' || status === 'evaluation_failed') {
    return {
      selectedChapter: selectedChapter.value,
      chapterGenerationResult: props.chapterGenerationResult,
      availableVersions: props.availableVersions,
      groupedVersions: props.groupedVersions,
      selectedVersionIndex: props.selectedVersionIndex,
      isSelectingVersion: props.isSelectingVersion,
      evaluatingChapter: props.evaluatingChapter,
      isEvaluationFailed: isChapterEvaluationFailed(props.selectedChapterNumber)
    }
  }
  if (selectedChapter.value?.content) {
    return { selectedChapter: selectedChapter.value, detectionState: detectionState.value }
  }
  if (isChapterFailed(props.selectedChapterNumber)) {
    return {
      chapterNumber: props.selectedChapterNumber,
      generatingChapter: props.generatingChapter
    }
  }
  return {
    chapterNumber: props.selectedChapterNumber,
    generatingChapter: props.generatingChapter,
    canGenerate: canGenerateChapter(props.selectedChapterNumber)
  }
})
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
