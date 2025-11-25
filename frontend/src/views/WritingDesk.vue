<template>
  <div class="h-screen flex flex-col bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
    <WDHeader
      :project="project"
      :progress="progress"
      :completed-chapters="completedChapters"
      :total-chapters="totalChapters"
      @go-back="goBack"
      @view-project-detail="viewProjectDetail"
      @toggle-sidebar="toggleSidebar"
    />

    <!-- 主要内容区域 -->
    <div class="flex-1 w-full px-4 sm:px-6 lg:px-8 py-6 overflow-hidden min-h-0">
      <!-- 加载状态 -->
      <div v-if="novelStore.isLoading" class="h-full flex justify-center items-center">
        <div class="text-center">
          <div class="w-12 h-12 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mx-auto mb-4"></div>
          <p class="text-gray-600">正在加载项目数据...</p>
        </div>
      </div>

      <!-- 错误状态 -->
      <div v-else-if="novelStore.error" class="text-center py-20">
        <div class="bg-red-50 border border-red-200 rounded-xl p-8 max-w-md mx-auto">
          <svg class="w-12 h-12 text-red-400 mx-auto mb-4" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd"></path>
          </svg>
          <h3 class="text-lg font-semibold text-red-900 mb-2">加载失败</h3>
          <p class="text-red-700 mb-4">{{ novelStore.error }}</p>
          <button
            @click="loadProject"
            class="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
          >
            重新加载
          </button>
        </div>
      </div>

      <!-- 主要内容 -->
      <div v-else-if="project" class="h-full min-h-0 flex gap-6">
        <WDSidebar
          :project="project"
          :sidebar-open="sidebarOpen"
          :selected-chapter-number="selectedChapterNumber"
          :generating-chapter="generatingChapter"
          :evaluating-chapter="evaluatingChapter"
          :is-generating-outline="isGeneratingOutline"
          @close-sidebar="closeSidebar"
          @select-chapter="selectChapter"
          @generate-chapter="generateChapter"
          @edit-chapter="openEditChapterModal"
          @delete-chapter="deleteChapter"
          @generate-outline="generateOutline"
        />

        <div class="flex-1 min-w-0 min-h-0 flex flex-col gap-4">
          <section class="bg-white/70 backdrop-blur-xl rounded-2xl shadow-lg border border-indigo-100/60 px-3 py-2 sm:px-4 sm:py-3">
            <div class="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3 lg:gap-6">
              <div class="flex-shrink-0 flex flex-col gap-1 max-w-[360px]">
                <div class="flex items-center gap-2 flex-wrap">
                  <div class="flex items-center gap-1">
                    <h3 class="text-sm font-semibold text-indigo-800">写作模型选择</h3>
                    <span
                      v-if="loadingWritingModels"
                      class="text-[11px] text-indigo-400"
                    >
                      加载中...
                    </span>
                  </div>
                  <div class="flex items-center gap-1.5 text-[11px] text-indigo-600">
                    <button
                      v-if="writingModelOptionsEnabled && writingModelOptions.length > 0"
                      type="button"
                      class="px-2 py-1 border border-indigo-200 text-indigo-600 rounded-md hover:bg-indigo-50 transition"
                      @click="toggleSelectAllModels"
                    >
                      {{ isAllModelsSelected ? '清空写手' : '全军出击' }}
                    </button>
                    <button
                      type="button"
                      class="px-2 py-1 border border-slate-200 text-slate-600 rounded-md hover:bg-slate-50 transition"
                      @click="loadWritingModelOptions"
                    >
                      刷新写手
                    </button>
                  </div>
                </div>
                <p class="text-[11px] text-indigo-500 leading-tight">
                  主模型始终参与，点击头像可选择附加模型或在生成过程中手动停止。
                </p>
                <p class="text-[11px] text-slate-500 leading-tight">
                  <template v-if="writingModelOptionsEnabled && writingModelOptions.length > 0">
                    已启用 {{ writingModelOptions.length }} 个附加模型，可随时切换或停止。
                  </template>
                  <template v-else>
                    当前仅主模型参与写作，可在设置中开启附加模型以生成更多版本。
                  </template>
                </p>
                <p
                  v-if="activeModelSummary.total > 0"
                  class="text-[11px] text-slate-500 leading-tight"
                >
                  <template v-if="activeModelSummary.running > 0">
                    {{ activeModelSummary.running }} 个模型生成中，已完成 {{ activeModelSummary.completed + activeModelSummary.stopped + activeModelSummary.failed }} 个。
                  </template>
                  <template v-else>
                    所有模型已完成，可进入版本评估。
                  </template>
                </p>
                <div class="flex flex-wrap items-center gap-3 text-[11px] text-slate-600 pt-1">
                  <span class="font-medium text-indigo-600">错误处理：</span>
                  <label class="inline-flex items-center gap-1 cursor-pointer">
                    <input
                      type="radio"
                      class="h-3 w-3 text-indigo-600 border-slate-300 focus:ring-indigo-500"
                    value="stop"
                    v-model="errorHandlingMode"
                  >
                  遇错即停
                </label>
                <label class="inline-flex items-center gap-1 cursor-pointer">
                  <input
                    type="radio"
                    class="h-3 w-3 text-indigo-600 border-slate-300 focus:ring-indigo-500"
                    value="continue"
                    v-model="errorHandlingMode"
                  >
                  遇错继续
                </label>
              </div>
              </div>
              <div class="flex flex-1 items-start ml-3">
                <WritingModelAvatarList
                  :models="modelAvatarItems"
                  :updating-key="variantUpdateBusyKey"
                  @toggle="handleAvatarToggle"
                  @stop="handleAvatarStop"
                  @update-variants="handleVariantUpdate"
                />
              </div>
            </div>
          </section>

          <WDWorkspace
            :project="project"
            :selected-chapter-number="selectedChapterNumber"
          :generating-chapter="generatingChapter"
          :evaluating-chapter="evaluatingChapter"
          :show-version-selector="showVersionSelector"
          :chapter-generation-result="chapterGenerationResult"
          :selected-version-index="selectedVersionIndex"
          :available-versions="availableVersions"
          :grouped-versions="groupedVersions"
          :is-selecting-version="isSelectingVersion"
          :is-saving-content="savingChapterContent"
          @regenerate-chapter="regenerateChapter"
          @evaluate-chapter="evaluateChapter"
          @hide-version-selector="hideVersionSelector"
          @update:selected-version-index="selectedVersionIndex = $event"
          @show-version-detail="showVersionDetail"
          @confirm-version-selection="confirmVersionSelection"
          @generate-chapter="generateChapter"
          @show-evaluation-detail="showEvaluationDetailModal = true"
          @fetch-chapter-status="fetchChapterStatus"
          @edit-chapter="editChapterContent"
          />
        </div>
      </div>
    </div>
    <WDVersionDetailModal
      :show="showVersionDetailModal"
      :detail-version-index="detailVersionIndex"
      :version="availableVersions[detailVersionIndex]"
      :is-current="isCurrentVersion(detailVersionIndex)"
      @close="closeVersionDetail"
      @select-version="selectVersionFromDetail"
    />
    <WDEvaluationDetailModal
      :show="showEvaluationDetailModal"
      :evaluation="selectedChapter?.evaluation || null"
      :evaluation-time="selectedChapter?.evaluation_created_at || null"
      @close="showEvaluationDetailModal = false"
    />
    <WDEditChapterModal
      :show="showEditChapterModal"
      :chapter="editingChapter"
      :saving="savingChapterOutline"
      @close="closeEditChapterModal"
      @save="saveChapterChanges"
    />
    <WDGenerateOutlineModal
      :show="showGenerateOutlineModal"
      @close="showGenerateOutlineModal = false"
      @generate="handleGenerateOutline"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useNovelStore } from '@/stores/novel'
import { NovelAPI } from '@/api/novel'
import type {
  Chapter,
  ChapterOutline,
  ChapterGenerationResponse,
  ChapterVersion,
  WritingModelOption
} from '@/api/novel'
import { globalAlert } from '@/composables/useAlert'
import WDHeader from '@/components/writing-desk/WDHeader.vue'
import WDSidebar from '@/components/writing-desk/WDSidebar.vue'
import WDWorkspace from '@/components/writing-desk/WDWorkspace.vue'
import WDVersionDetailModal from '@/components/writing-desk/WDVersionDetailModal.vue'
import WDEvaluationDetailModal from '@/components/writing-desk/WDEvaluationDetailModal.vue'
import WDEditChapterModal from '@/components/writing-desk/WDEditChapterModal.vue'
import WDGenerateOutlineModal from '@/components/writing-desk/WDGenerateOutlineModal.vue'
import WritingModelAvatarList from '@/components/writing-desk/WritingModelAvatarList.vue'
import type { WritingModelAvatarItem, WritingModelAvatarStatus } from '@/components/writing-desk/modelAvatarTypes'

interface Props {
  id: string
}

const props = defineProps<Props>()
const router = useRouter()
const novelStore = useNovelStore()

interface ModelRuntimeState {
  status: WritingModelAvatarStatus
  targetVariants: number
  currentVariant: number
  startedAt: number | null
  finishedAt: number | null
  errorMessage?: string | null
}

interface ModelConfig {
  key: string
  displayName: string
  provider?: string | null
  isPrimary: boolean
  variants: number
}

const ERROR_STRATEGY_STORAGE_KEY = 'writing_error_strategy'
const errorHandlingMode = ref<'stop' | 'continue'>('stop')

// 状态管理
const selectedChapterNumber = ref<number | null>(null)
const chapterGenerationResult = ref<ChapterGenerationResponse | null>(null)
const selectedVersionIndex = ref<number>(0)
const generatingChapter = ref<number | null>(null)
const sidebarOpen = ref(false)
const showVersionDetailModal = ref(false)
const detailVersionIndex = ref<number>(0)
const showEvaluationDetailModal = ref(false)
const showEditChapterModal = ref(false)
const editingChapter = ref<ChapterOutline | null>(null)
const savingChapterContent = ref(false)
const savingChapterOutline = ref(false)
const isGeneratingOutline = ref(false)
const showGenerateOutlineModal = ref(false)

const writingModelOptionsEnabled = ref(false)
const writingModelOptions = ref<WritingModelOption[]>([])
const selectedModelKeys = ref<string[]>([])
const modelSelectionInitialized = ref(false)
const previousSelectedModelKeys = ref<string[]>([])
const writingModelFallbackVariants = ref(0)
const activeRuntimeChapter = ref<number | null>(null)
const generationCompletionNotified = ref<Record<number, boolean>>({})
const loadingWritingModels = ref(false)
const evaluatingInFlight = ref(false)
const variantUpdateBusyKey = ref<string | null>(null)

onMounted(() => {
  if (typeof window !== 'undefined') {
    const stored = window.localStorage.getItem(ERROR_STRATEGY_STORAGE_KEY)
    if (stored === 'continue' || stored === 'stop') {
      errorHandlingMode.value = stored
    }
  }
})

watch(errorHandlingMode, (value) => {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(ERROR_STRATEGY_STORAGE_KEY, value)
  }
})

const modelStates = ref<Record<string, ModelRuntimeState>>({})

const avatarPalette = [
  { base: '#6366F1', accent: '#8B5CF6' },
  { base: '#0EA5E9', accent: '#22D3EE' },
  { base: '#F97316', accent: '#FB923C' },
  { base: '#14B8A6', accent: '#2DD4BF' },
  { base: '#F43F5E', accent: '#FB7185' },
  { base: '#EC4899', accent: '#F472B6' },
  { base: '#10B981', accent: '#34D399' },
  { base: '#8B5CF6', accent: '#A855F7' }
]

const hashString = (value: string): number => {
  let hash = 0
  for (let i = 0; i < value.length; i += 1) {
    hash = (hash << 5) - hash + value.charCodeAt(i)
    hash |= 0
  }
  return Math.abs(hash)
}

const getAvatarTheme = (key: string) => {
  const palette = avatarPalette[hashString(key) % avatarPalette.length]
  return {
    color: palette.base,
    accent: palette.accent
  }
}

const createInitials = (name: string) => {
  const trimmed = name.trim()
  if (!trimmed) return 'M'
  const chars = trimmed.replace(/\s+/g, '')
  const take = chars.slice(0, 2)
  return take
    .split('')
    .map(ch => (/[a-z]/i.test(ch) ? ch.toUpperCase() : ch))
    .join('') || 'M'
}

// 计算属性
const project = computed(() => novelStore.currentProject)

const selectedChapter = computed(() => {
  if (!project.value || selectedChapterNumber.value === null) return null
  return project.value.chapters.find(ch => ch.chapter_number === selectedChapterNumber.value) || null
})

const showVersionSelector = computed(() => {
  if (!selectedChapter.value) return false
  const status = selectedChapter.value.generation_status
  return status === 'waiting_for_confirm' || status === 'evaluating' || status === 'evaluation_failed' || status === 'selecting'
})

const baseModelConfigs = computed<ModelConfig[]>(() => {
  const fallbackVariants = Math.max(writingModelFallbackVariants.value || 1, 1)
  const configs: ModelConfig[] = [
    {
      key: 'primary',
      displayName: '主模型',
      provider: 'primary',
      isPrimary: true,
      variants: fallbackVariants
    }
  ]
  if (writingModelOptionsEnabled.value) {
    writingModelOptions.value.forEach((option) => {
      configs.push({
        key: option.key,
        displayName: option.display_name || option.key,
        provider: option.provider,
        isPrimary: false,
        variants: Math.max(option.variants || fallbackVariants, 1)
      })
    })
  }
  return configs
})

const ensureModelState = (modelKey: string, overrides?: Partial<ModelRuntimeState>) => {
  const config = baseModelConfigs.value.find(item => item.key === modelKey)
  const defaultTarget = Math.max(config?.variants || writingModelFallbackVariants.value || 1, 1)
  if (!modelStates.value[modelKey]) {
    modelStates.value[modelKey] = {
      status: 'idle',
      targetVariants: defaultTarget,
      currentVariant: 0,
      startedAt: null,
      finishedAt: null,
      errorMessage: null
    }
  }
  if (overrides) {
    const nextTarget = overrides.targetVariants !== undefined ? Math.max(overrides.targetVariants, 1) : modelStates.value[modelKey].targetVariants || defaultTarget
    modelStates.value[modelKey] = {
      ...modelStates.value[modelKey],
      ...overrides,
      targetVariants: nextTarget
    }
  } else if (!modelStates.value[modelKey].targetVariants) {
    modelStates.value[modelKey].targetVariants = defaultTarget
  }
  return modelStates.value[modelKey]
}

const resetModelStatesForChapter = (_chapterNumber: number | null) => {
  const fallback = Math.max(writingModelFallbackVariants.value || 1, 1)

  baseModelConfigs.value.forEach((config) => {
    const isSelected = config.isPrimary || selectedModelKeys.value.includes(config.key)
    const defaultStatus: WritingModelAvatarStatus = isSelected ? 'selected' : 'idle'
    const defaultTarget = Math.max(config.variants || fallback, 1)

    ensureModelState(config.key, {
      status: defaultStatus,
      currentVariant: 0,
      startedAt: null,
      finishedAt: null,
      errorMessage: null,
      targetVariants: defaultTarget
    })
  })
}

watch(
  baseModelConfigs,
  (configs) => {
    const keys = configs.map(item => item.key)
    configs.forEach(config => ensureModelState(config.key, { targetVariants: config.variants }))
    Object.keys(modelStates.value).forEach((key) => {
      if (!keys.includes(key)) {
        delete modelStates.value[key]
      }
    })
  },
  { immediate: true, deep: true }
)

const modelAvatarItems = computed<WritingModelAvatarItem[]>(() => {
  return baseModelConfigs.value.map((config) => {
    const runtime = ensureModelState(config.key)
    const selected = config.isPrimary || selectedModelKeys.value.includes(config.key)
    let status: WritingModelAvatarStatus = runtime.status
    if (status === 'idle') {
      status = selected ? 'selected' : 'idle'
    }
    if (status === 'selected' && !selected) {
      status = 'idle'
    }
    if (config.isPrimary && status === 'selected') {
      status = 'selected'
    }
    const theme = getAvatarTheme(config.key)
    return {
      key: config.key,
      displayName: config.displayName,
      isPrimary: config.isPrimary,
      selected,
      status,
      targetVariants: Math.max(runtime.targetVariants || config.variants || 1, 1),
      currentVariant: runtime.currentVariant,
      startedAt: runtime.startedAt,
      finishedAt: runtime.finishedAt,
      canStop: !config.isPrimary,
      canToggle: !config.isPrimary,
      avatarColor: theme.color,
      avatarAccent: theme.accent,
      initials: createInitials(config.displayName),
      errorMessage: runtime.errorMessage || null
    }
  })
})

const activeModelSummary = computed(() => {
  const activeItems = modelAvatarItems.value.filter(item => item.isPrimary || item.selected)
  const running = activeItems.filter(item => item.status === 'generating' || item.status === 'stopping').length
  const completed = activeItems.filter(item => item.status === 'completed').length
  const stopped = activeItems.filter(item => item.status === 'stopped').length
  const failed = activeItems.filter(item => item.status === 'error').length
  const awaiting = activeItems.filter(item => item.status === 'selected' || item.status === 'idle' || item.status === 'queued').length
  return {
    total: activeItems.length,
    running,
    completed,
    stopped,
    failed,
    awaiting
  }
})

const mapProgressStatus = (status: string): WritingModelAvatarStatus => {
  switch (status) {
    case 'pending':
      return 'queued'
    case 'generating':
      return 'generating'
    case 'stopping':
      return 'stopping'
    case 'completed':
      return 'completed'
    case 'stopped':
      return 'stopped'
    case 'error':
      return 'error'
    default:
      return 'idle'
  }
}

const syncModelProgress = async (chapterNumber: number | null = selectedChapterNumber.value) => {
  if (chapterNumber === null) {
    return
  }
  try {
    const progress = await novelStore.getChapterGenerationProgress(chapterNumber)
    const seenKeys = new Set<string>()
    progress.models.forEach((model) => {
      const status = mapProgressStatus(model.status)
      const startedAt = model.started_at ? new Date(model.started_at).getTime() : null
      const finishedAt = model.finished_at ? new Date(model.finished_at).getTime() : null
      ensureModelState(model.model_key, {
        status,
        targetVariants: model.total_variants || undefined,
        currentVariant: model.completed_variants ?? 0,
        startedAt,
        finishedAt,
        errorMessage: model.error_message || null
      })
      seenKeys.add(model.model_key)
    })
    if (!seenKeys.has('primary')) {
      ensureModelState('primary')
    }
  } catch (error) {
    console.error('获取模型进度失败:', error)
  }
}

const prepareModelStatesForGeneration = (selectedKeys: string[]) => {
  const now = Date.now()
  const activeKeys = new Set<string>(['primary', ...selectedKeys])
  baseModelConfigs.value.forEach((config) => {
    if (config.isPrimary) {
      ensureModelState(config.key, {
        status: 'generating',
        currentVariant: 0,
        targetVariants: config.variants,
        startedAt: now,
        finishedAt: null,
        errorMessage: null
      })
      return
    }
    if (activeKeys.has(config.key)) {
      ensureModelState(config.key, {
        status: 'queued',
        currentVariant: 0,
        targetVariants: config.variants,
        startedAt: null,
        finishedAt: null,
        errorMessage: null
      })
      return
    }
    const fallbackStatus: WritingModelAvatarStatus = selectedModelKeys.value.includes(config.key) ? 'selected' : 'idle'
    ensureModelState(config.key, {
      status: fallbackStatus,
      currentVariant: 0,
      startedAt: null,
      finishedAt: null,
      errorMessage: null
    })
  })
}

const markGenerationFailure = (keys: string[], message: string) => {
  const now = Date.now()
  keys.forEach((key) => {
    ensureModelState(key, {
      status: 'error',
      finishedAt: now,
      errorMessage: message
    })
  })
}

const handleAvatarToggle = (modelKey: string) => {
  if (modelKey === 'primary') {
    return
  }
  if (selectedModelKeys.value.includes(modelKey)) {
    selectedModelKeys.value = selectedModelKeys.value.filter(key => key !== modelKey)
  } else {
    selectedModelKeys.value = [...selectedModelKeys.value, modelKey]
  }
}

const handleAvatarStop = async (modelKey: string) => {
  if (selectedChapterNumber.value === null) {
    return
  }
  const runtime = ensureModelState(modelKey)
  if (runtime.status === 'stopping') {
    return
  }
  const confirmed = window.confirm('确定要停止该模型的章节生成吗？')
  if (!confirmed) {
    return
  }
  ensureModelState(modelKey, { status: 'stopping' })
  try {
    await novelStore.stopModelGeneration(selectedChapterNumber.value, modelKey)
    globalAlert.showSuccess('已提交停止请求', '操作成功')
    await syncModelProgress(selectedChapterNumber.value)
  } catch (error) {
    console.error('停止模型失败:', error)
    ensureModelState(modelKey, { status: 'generating' })
    globalAlert.showError(`停止模型失败: ${error instanceof Error ? error.message : '未知错误'}`, '操作失败')
  }
}

const handleVariantUpdate = async ({ modelKey, variants }: { modelKey: string; variants: number }) => {
  if (variantUpdateBusyKey.value) {
    return
  }
  const normalized = Math.max(1, Math.min(Math.round(variants), 10))
  variantUpdateBusyKey.value = modelKey
  try {
    const response = await NovelAPI.updateWritingModelVariants(modelKey, normalized)
    writingModelOptionsEnabled.value = response.enabled
    writingModelFallbackVariants.value = response.fallback_variants
    writingModelOptions.value = response.models
    baseModelConfigs.value.forEach((config) => {
      const nextTarget = Math.max(config.variants || writingModelFallbackVariants.value || 1, 1)
      ensureModelState(config.key, { targetVariants: nextTarget })
    })
    globalAlert.showSuccess('已更新生成版本数', '设置成功')
  } catch (error) {
    console.error('更新模型版本数失败:', error)
    globalAlert.showError(`更新版本数失败: ${error instanceof Error ? error.message : '未知错误'}`, '设置失败')
  } finally {
    variantUpdateBusyKey.value = null
  }
}

const evaluatingChapter = computed(() => {
  if (selectedChapter.value?.generation_status === 'evaluating') {
    return selectedChapter.value.chapter_number
  }
  if (evaluatingInFlight.value && selectedChapterNumber.value !== null) {
    return selectedChapterNumber.value
  }
  return null
})

const isSelectingVersion = computed(() => {
  return selectedChapter.value?.generation_status === 'selecting'
})

const selectedChapterOutline = computed(() => {
  if (!project.value?.blueprint?.chapter_outline || selectedChapterNumber.value === null) return null
  return project.value.blueprint.chapter_outline.find(ch => ch.chapter_number === selectedChapterNumber.value) || null
})

const progress = computed(() => {
  if (!project.value?.blueprint?.chapter_outline) return 0
  const totalChapters = project.value.blueprint.chapter_outline.length
  const completedChapters = project.value.chapters.filter(ch => ch.content).length
  return Math.round((completedChapters / totalChapters) * 100)
})

const totalChapters = computed(() => {
  return project.value?.blueprint?.chapter_outline?.length || 0
})

const completedChapters = computed(() => {
  return project.value?.chapters?.filter(ch => ch.content)?.length || 0
})

const isCurrentVersion = (versionIndex: number) => {
  if (!selectedChapter.value?.content || !availableVersions.value?.[versionIndex]?.content) return false

  // 使用cleanVersionContent函数清理内容进行比较
  const cleanCurrentContent = cleanVersionContent(selectedChapter.value.content)
  const cleanVersionContentStr = cleanVersionContent(availableVersions.value[versionIndex].content)

  return cleanCurrentContent === cleanVersionContentStr
}

const cleanVersionContent = (content: string): string => {
  if (!content) return ''

  // 尝试解析JSON，看是否是完整的章节对象
  try {
    const parsed = JSON.parse(content)
    if (parsed && typeof parsed === 'object' && parsed.content) {
      // 如果是章节对象，提取content字段
      content = parsed.content
    }
  } catch (error) {
    // 如果不是JSON，继续处理字符串
  }

  // 去掉开头和结尾的引号
  let cleaned = content.replace(/^"|"$/g, '')

  // 处理转义字符
  cleaned = cleaned.replace(/\\n/g, '\n')  // 换行符
  cleaned = cleaned.replace(/\\"/g, '"')   // 引号
  cleaned = cleaned.replace(/\\t/g, '\t')  // 制表符
  cleaned = cleaned.replace(/\\\\/g, '\\') // 反斜杠

  return cleaned
}

const canGenerateChapter = (chapterNumber: number) => {
  if (!project.value?.blueprint?.chapter_outline) return false

  // 检查前面所有章节是否都已成功生成
  const outlines = project.value.blueprint.chapter_outline.sort((a, b) => a.chapter_number - b.chapter_number)
  
  for (const outline of outlines) {
    if (outline.chapter_number >= chapterNumber) break
    
    const chapter = project.value?.chapters.find(ch => ch.chapter_number === outline.chapter_number)
    if (!chapter || chapter.generation_status !== 'successful') {
      return false // 前面有章节未完成
    }
  }

  // 检查当前章节是否已经完成
  const currentChapter = project.value?.chapters.find(ch => ch.chapter_number === chapterNumber)
  if (currentChapter && currentChapter.generation_status === 'successful') {
    return true // 已完成的章节可以重新生成
  }

  return true // 前面章节都完成了，可以生成当前章节
}

const isChapterFailed = (chapterNumber: number) => {
  if (!project.value?.chapters) return false
  const chapter = project.value.chapters.find(ch => ch.chapter_number === chapterNumber)
  return chapter && chapter.generation_status === 'failed'
}

const hasChapterInProgress = (chapterNumber: number) => {
  if (!project.value?.chapters) return false
  const chapter = project.value.chapters.find(ch => ch.chapter_number === chapterNumber)
  // waiting_for_confirm状态表示等待选择版本 = 进行中状态
  return chapter && chapter.generation_status === 'waiting_for_confirm'
}

// 可用版本列表 (合并生成结果和已有版本)
const availableVersions = computed(() => {
  const normalize = (version: any): ChapterVersion => {
    if (typeof version === 'string') {
      return {
        content: version,
        metadata: {},
        provider: 'legacy',
        label: undefined
      }
    }
    return {
      content: version.content || '',
      metadata: version.metadata || {},
      provider: version.provider,
      label: version.label
    }
  }

  if (chapterGenerationResult.value?.versions) {
    return chapterGenerationResult.value.versions.map(normalize)
  }

  if (selectedChapter.value?.versions && Array.isArray(selectedChapter.value.versions)) {
    return selectedChapter.value.versions.map(normalize)
  }

  return []
})

const groupedVersions = computed(() => {
  const groups = new Map<string, { modelKey: string; modelName: string; provider?: string | null; items: Array<{ version: ChapterVersion; globalIndex: number }> }>()
  availableVersions.value.forEach((version, index) => {
    const metadata = version.metadata || {}
    const modelKey = metadata.model_key || version.provider || 'primary'
    const modelName = metadata.model_name || version.label || (modelKey === 'primary' ? '主模型' : modelKey)
    if (!groups.has(modelKey)) {
      groups.set(modelKey, { modelKey, modelName, provider: version.provider, items: [] })
    }
    groups.get(modelKey)!.items.push({ version, globalIndex: index })
  })
  return Array.from(groups.values())
})

const ensureWritingModelSelection = () => {
  const availableKeys = writingModelOptions.value.map(model => model.key)
  const hasOptions = availableKeys.length > 0

  const filteredSelection = selectedModelKeys.value.filter(key => availableKeys.includes(key))
  const selectionChanged = filteredSelection.length !== selectedModelKeys.value.length
  selectedModelKeys.value = filteredSelection

  if (!writingModelOptionsEnabled.value || !hasOptions) {
    if (!hasOptions) {
      modelSelectionInitialized.value = false
    }
    return
  }

  if (!modelSelectionInitialized.value) {
    if (selectedModelKeys.value.length === 0) {
      selectedModelKeys.value = [...availableKeys]
    }
    modelSelectionInitialized.value = true
    return
  }

  if (selectionChanged && selectedModelKeys.value.length === 0) {
    return
  }
}

const syncVariantsFromGroupedVersions = () => {
  groupedVersions.value.forEach((group) => {
    const runtime = ensureModelState(group.modelKey)
    if (runtime.status !== 'generating' && runtime.status !== 'stopping') {
      runtime.currentVariant = group.items.length
    }
    if (group.items.length > 0 && runtime.targetVariants < group.items.length) {
      runtime.targetVariants = group.items.length
    }
  })
}

watch(
  groupedVersions,
  () => {
    syncVariantsFromGroupedVersions()
  },
  { deep: true, immediate: true }
)

watch(
  selectedModelKeys,
  () => {
    baseModelConfigs.value.forEach((config) => {
      if (config.isPrimary) return
      const runtime = ensureModelState(config.key)
      if (runtime.status === 'generating' || runtime.status === 'stopping') {
        return
      }
      runtime.status = selectedModelKeys.value.includes(config.key) ? 'selected' : 'idle'
      runtime.startedAt = null
      runtime.finishedAt = null
      runtime.currentVariant = 0
      runtime.errorMessage = null
    })
  },
  { deep: true }
)

watch(
  () => selectedChapter.value?.generation_status,
  (status, prevStatus) => {
    if (!status) {
      return
    }
    const chapterNumber = selectedChapterNumber.value
    if (chapterNumber !== null) {
      if (status === 'generating') {
        generationCompletionNotified.value[chapterNumber] = false
      }
      const doneStatuses = ['waiting_for_confirm', 'successful'] as const
      const wasGenerating = ['generating', 'evaluating', 'selecting'].includes(prevStatus || '')
      const stillMarkingGenerating = generatingChapter.value === chapterNumber
      if (
        doneStatuses.includes(status as (typeof doneStatuses)[number]) &&
        wasGenerating &&
        !generationCompletionNotified.value[chapterNumber] &&
        !stillMarkingGenerating
      ) {
        generationCompletionNotified.value[chapterNumber] = true
        globalAlert.showSuccess('章节生成完成，可查看版本或正文。', '生成完成')
      }
      if (status !== 'generating' && generatingChapter.value === chapterNumber) {
        generatingChapter.value = null
      }
    }
    if (status === 'generating' && selectedChapterNumber.value !== null) {
      activeRuntimeChapter.value = selectedChapterNumber.value
      syncModelProgress(selectedChapterNumber.value)
      return
    }
    if (['waiting_for_confirm', 'successful', 'selecting', 'evaluation_failed'].includes(status)) {
      if (activeRuntimeChapter.value !== selectedChapterNumber.value) {
        return
      }
      groupedVersions.value.forEach((group) => {
        if (group.items.length === 0) return
        const runtime = ensureModelState(group.modelKey)
        if (runtime.status !== 'completed' && runtime.status !== 'error') {
          runtime.status = 'completed'
          runtime.finishedAt = runtime.finishedAt ?? Date.now()
        }
      })
      activeRuntimeChapter.value = null
    }
  },
  { immediate: true }
)

watch(
  selectedChapterNumber,
  (chapterNumber) => {
    resetModelStatesForChapter(chapterNumber)
    if (chapterNumber !== activeRuntimeChapter.value) {
      activeRuntimeChapter.value = null
    }
    if (chapterNumber !== null) {
      const chapterStatus = project.value?.chapters.find(ch => ch.chapter_number === chapterNumber)?.generation_status
      if (chapterStatus === 'generating') {
        activeRuntimeChapter.value = chapterNumber
        syncModelProgress(chapterNumber)
      } else if (['waiting_for_confirm', 'selecting', 'evaluation_failed'].includes(chapterStatus ?? '')) {
        syncModelProgress(chapterNumber)
      }
    }
  },
  { immediate: true }
)

// 方法
const goBack = () => {
  router.push('/workspace')
}

const viewProjectDetail = () => {
  if (project.value) {
    router.push(`/detail/${project.value.id}`)
  }
}

const toggleSidebar = () => {
  sidebarOpen.value = !sidebarOpen.value
}

const closeSidebar = () => {
  sidebarOpen.value = false
}

const loadProject = async () => {
  try {
    await novelStore.loadProject(props.id)
  } catch (error) {
    console.error('加载项目失败:', error)
  }
}

const fetchChapterStatus = async () => {
  if (selectedChapterNumber.value === null) {
    return
  }
  if (evaluatingInFlight.value) {
    return
  }
  try {
    await novelStore.loadChapter(selectedChapterNumber.value)
    await syncModelProgress(selectedChapterNumber.value)
  } catch (error) {
    console.error('轮询章节状态失败:', error)
    // 在这里可以决定是否要通知用户轮询失败
  }
}

// 显示版本详情
const showVersionDetail = (versionIndex: number) => {
  detailVersionIndex.value = versionIndex
  showVersionDetailModal.value = true
}

// 关闭版本详情弹窗
const closeVersionDetail = () => {
  showVersionDetailModal.value = false
}

// 隐藏版本选择器，返回内容视图
const hideVersionSelector = () => {
  chapterGenerationResult.value = null
  selectedVersionIndex.value = 0
}

const selectChapter = (chapterNumber: number) => {
  selectedChapterNumber.value = chapterNumber
  chapterGenerationResult.value = null
  selectedVersionIndex.value = 0
  closeSidebar()
}

const loadWritingModelOptions = async () => {
  loadingWritingModels.value = true
  try {
    const response = await NovelAPI.getWritingModelOptions()
    writingModelFallbackVariants.value = response.fallback_variants
    writingModelOptionsEnabled.value = response.enabled
    writingModelOptions.value = response.models
    ensureWritingModelSelection()
  } catch (error) {
    console.error('加载写作模型选项失败:', error)
    writingModelOptionsEnabled.value = false
    writingModelOptions.value = []
    selectedModelKeys.value = []
    previousSelectedModelKeys.value = []
    modelSelectionInitialized.value = false
  } finally {
    loadingWritingModels.value = false
  }
}

const toggleSelectAllModels = () => {
  if (!writingModelOptionsEnabled.value) return
  if (selectedModelKeys.value.length === writingModelOptions.value.length) {
    selectedModelKeys.value = []
  } else {
    selectedModelKeys.value = writingModelOptions.value.map(model => model.key)
  }
}

const isAllModelsSelected = computed(
  () =>
    writingModelOptions.value.length > 0 &&
    selectedModelKeys.value.length === writingModelOptions.value.length
)

watch(writingModelOptionsEnabled, (enabled) => {
  if (!enabled) {
    previousSelectedModelKeys.value = [...selectedModelKeys.value]
    selectedModelKeys.value = []
    modelSelectionInitialized.value = false
    return
  }

  const availableKeys = new Set(writingModelOptions.value.map(model => model.key))
  const restoredKeys = previousSelectedModelKeys.value.filter(key => availableKeys.has(key))
  previousSelectedModelKeys.value = []

  if (restoredKeys.length > 0) {
    selectedModelKeys.value = restoredKeys
    modelSelectionInitialized.value = true
    return
  }

  modelSelectionInitialized.value = false
  ensureWritingModelSelection()
}, { flush: 'post' })

watch(
  () => writingModelOptions.value,
  () => {
    ensureWritingModelSelection()
  },
  { deep: true }
)

const ensureLocalChapter = (chapterNumber: number): Chapter | null => {
  if (!project.value) return null
  if (!Array.isArray(project.value.chapters)) {
    project.value.chapters = []
  }
  let chapter = project.value.chapters.find(ch => ch.chapter_number === chapterNumber) || null
  if (!chapter) {
    const outline = project.value.blueprint?.chapter_outline?.find(o => o.chapter_number === chapterNumber)
    chapter = {
      chapter_number: chapterNumber,
      title: outline?.title || `第${chapterNumber}章`,
      summary: outline?.summary || '',
      real_summary: null,
      content: '',
      versions: [],
      evaluation: null,
      evaluation_created_at: null,
      generation_status: 'not_generated'
    } as Chapter
    project.value.chapters.push(chapter)
  }
  return chapter
}

const generateChapter = async (payload: number | { chapterNumber: number; formatCleanup?: boolean }) => {
  const { chapterNumber, formatCleanup } =
    typeof payload === 'number' ? { chapterNumber: payload, formatCleanup: undefined } : payload

  // 检查是否可以生成该章节
  if (!canGenerateChapter(chapterNumber) && !isChapterFailed(chapterNumber) && !hasChapterInProgress(chapterNumber)) {
    globalAlert.showError('请按顺序生成章节，先完成前面的章节', '生成受限')
    return
  }

  const optionalKeysForGenerationBase = baseModelConfigs.value
    .filter(config => !config.isPrimary && selectedModelKeys.value.includes(config.key))
    .map(config => config.key)
  let optionalKeysForGeneration: string[] = optionalKeysForGenerationBase
  try {
    resetModelStatesForChapter(chapterNumber)
    activeRuntimeChapter.value = chapterNumber
    generatingChapter.value = chapterNumber
    selectedChapterNumber.value = chapterNumber

    // 在本地更新章节状态为generating
    const localChapter = ensureLocalChapter(chapterNumber)
    if (localChapter) {
      localChapter.generation_status = 'generating'
      localChapter.content = localChapter.content || ''
      localChapter.versions = localChapter.versions || []
    }

    let modelKeysForRequest: string[] | undefined
    if (writingModelOptionsEnabled.value) {
      const validKeys = writingModelOptions.value.map(option => option.key)
      const sanitized = optionalKeysForGeneration.filter(key => validKeys.includes(key))
      if (sanitized.length > 0) {
        modelKeysForRequest = sanitized
        optionalKeysForGeneration = sanitized
      } else if (optionalKeysForGeneration.length === 0) {
        // 用户显式取消所有附加模型
        modelKeysForRequest = []
        optionalKeysForGeneration = []
      } else if (validKeys.length === 0) {
        modelKeysForRequest = []
        optionalKeysForGeneration = []
      } else {
        modelKeysForRequest = validKeys
        optionalKeysForGeneration = validKeys
        selectedModelKeys.value = [...validKeys]
      }
    }

    prepareModelStatesForGeneration(optionalKeysForGeneration)
    await novelStore.generateChapter(chapterNumber, modelKeysForRequest, errorHandlingMode.value, formatCleanup)
    await novelStore.loadChapter(chapterNumber)
    await syncModelProgress(chapterNumber)

    const expectedVariants = baseModelConfigs.value.reduce((sum, config) => {
      if (config.isPrimary) {
        return sum + config.variants
      }
      if (optionalKeysForGeneration.includes(config.key)) {
        return sum + config.variants
      }
      return sum
    }, 0)
    const updatedChapter =
      project.value?.chapters.find(ch => ch.chapter_number === chapterNumber) || null
    if (errorHandlingMode.value === 'continue' && updatedChapter) {
      if (updatedChapter.generation_status === 'failed') {
        globalAlert.showError('所有写作版本均生成失败，请调整配置后重试。', '生成失败')
      } else {
        const actualVariants = updatedChapter.versions?.length ?? 0
        if (actualVariants < expectedVariants) {
          globalAlert.showAlert(
            `共有 ${expectedVariants - actualVariants} 个版本生成失败，系统已跳过并继续生成。`,
            'info',
            '生成警告'
          )
        }
      }
    }

    // store 中的 project 已经被更新，所以我们不需要手动修改本地状态
    // chapterGenerationResult 也不再需要，因为 availableVersions 会从更新后的 project.chapters 中获取数据
    // showVersionSelector is now a computed property and will update automatically.
    chapterGenerationResult.value = null
    selectedVersionIndex.value = 0
  } catch (error) {
    console.error('生成章节失败:', error)

    // 错误状态的本地更新仍然是必要的，以立即反映UI
    const localChapter = ensureLocalChapter(chapterNumber)
    if (localChapter) {
      localChapter.generation_status = 'failed'
      localChapter.content = localChapter.content || ''
    }

    const message = error instanceof Error ? error.message : '未知错误'
    markGenerationFailure(['primary', ...optionalKeysForGeneration], message)
    globalAlert.showError(`生成章节失败: ${message}`, '生成失败')
    await novelStore.loadChapter(chapterNumber).catch(() => {})
    if (activeRuntimeChapter.value === chapterNumber) {
      activeRuntimeChapter.value = null
    }
  } finally {
    generatingChapter.value = null
  }
}

const regenerateChapter = async (payload?: { formatCleanup?: boolean }) => {
  if (selectedChapterNumber.value !== null) {
    await generateChapter({ chapterNumber: selectedChapterNumber.value, formatCleanup: payload?.formatCleanup })
  }
}

const selectVersion = async (versionIndex: number) => {
  if (selectedChapterNumber.value === null || !availableVersions.value?.[versionIndex]?.content) {
    return
  }

  try {
    // 在本地立即更新状态以反映UI
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find(ch => ch.chapter_number === selectedChapterNumber.value)
      if (chapter) {
        chapter.generation_status = 'selecting'
      }
    }

    selectedVersionIndex.value = versionIndex
    await novelStore.selectChapterVersion(selectedChapterNumber.value, versionIndex)

    // 状态更新将由 store 自动触发，本地无需手动更新
    // 轮询机制会处理状态变更，成功后会自动隐藏选择器
    // showVersionSelector.value = false
    chapterGenerationResult.value = null
    globalAlert.showSuccess('版本已确认', '操作成功')
  } catch (error) {
    console.error('选择章节版本失败:', error)
    // 错误状态下恢复章节状态
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find(ch => ch.chapter_number === selectedChapterNumber.value)
      if (chapter) {
        chapter.generation_status = 'waiting_for_confirm' // Or the previous state
      }
    }
    globalAlert.showError(`选择章节版本失败: ${error instanceof Error ? error.message : '未知错误'}`, '选择失败')
  }
}

// 从详情弹窗中选择版本
const selectVersionFromDetail = async () => {
  selectedVersionIndex.value = detailVersionIndex.value
  await selectVersion(detailVersionIndex.value)
  closeVersionDetail()
}

const confirmVersionSelection = async () => {
  await selectVersion(selectedVersionIndex.value)
}

const saveChapterChanges = async (updatedChapter: ChapterOutline) => {
  try {
    savingChapterOutline.value = true
    await novelStore.updateChapterOutline(updatedChapter)
    globalAlert.showSuccess('章节大纲已更新', '保存成功')
    showEditChapterModal.value = false
  } catch (error) {
    console.error('更新章节大纲失败:', error)
    globalAlert.showError(`更新章节大纲失败: ${error instanceof Error ? error.message : '未知错误'}`, '保存失败')
  } finally {
    savingChapterOutline.value = false
  }
}

const closeEditChapterModal = () => {
  if (savingChapterOutline.value) {
    return
  }
  showEditChapterModal.value = false
}

const openEditChapterModal = (chapter: ChapterOutline) => {
  savingChapterOutline.value = false
  editingChapter.value = chapter
  showEditChapterModal.value = true
}

const evaluateChapter = async () => {
  if (selectedChapterNumber.value !== null) {
    let previousStatus: Chapter['generation_status'] | undefined
    try {
      // 在本地更新章节状态为evaluating以立即反映在UI上
      if (project.value?.chapters) {
        const chapter = project.value.chapters.find(ch => ch.chapter_number === selectedChapterNumber.value)
        if (chapter) {
          previousStatus = chapter.generation_status
          chapter.generation_status = 'evaluating'
        }
      }
      evaluatingInFlight.value = true
      await novelStore.evaluateChapter(selectedChapterNumber.value)
      
      // 评审完成后，状态会通过store和轮询更新，这里不需要额外操作
      globalAlert.showSuccess('章节评审结果已生成', '评审成功')
    } catch (error) {
      console.error('评审章节失败:', error)
      
      // 错误状态下恢复章节状态
      if (project.value?.chapters) {
        const chapter = project.value.chapters.find(ch => ch.chapter_number === selectedChapterNumber.value)
        if (chapter) {
          chapter.generation_status = previousStatus || chapter.generation_status || 'successful'
        }
      }
      
      globalAlert.showError(`评审章节失败: ${error instanceof Error ? error.message : '未知错误'}`, '评审失败')
    } finally {
      evaluatingInFlight.value = false
    }
  }
}

const deleteChapter = async (chapterNumbers: number | number[]) => {
  const numbersToDelete = Array.isArray(chapterNumbers) ? chapterNumbers : [chapterNumbers]
  const confirmationMessage = numbersToDelete.length > 1
    ? `您确定要删除选中的 ${numbersToDelete.length} 个章节吗？这个操作无法撤销。`
    : `您确定要删除第 ${numbersToDelete[0]} 章吗？这个操作无法撤销。`

  if (window.confirm(confirmationMessage)) {
    try {
      await novelStore.deleteChapter(numbersToDelete)
      globalAlert.showSuccess('章节已删除', '操作成功')
      // If the currently selected chapter was deleted, unselect it
      if (selectedChapterNumber.value && numbersToDelete.includes(selectedChapterNumber.value)) {
        selectedChapterNumber.value = null
      }
    } catch (error) {
      console.error('删除章节失败:', error)
      globalAlert.showError(`删除章节失败: ${error instanceof Error ? error.message : '未知错误'}`, '删除失败')
    }
  }
}

const generateOutline = async () => {
  showGenerateOutlineModal.value = true
}

const editChapterContent = async (data: { chapterNumber: number, content: string }) => {
  if (!project.value) return

  try {
    savingChapterContent.value = true
    await novelStore.editChapterContent(project.value.id, data.chapterNumber, data.content)
    globalAlert.showSuccess('章节内容已更新', '保存成功')
  } catch (error) {
    console.error('编辑章节内容失败:', error)
    globalAlert.showError(`编辑章节内容失败: ${error instanceof Error ? error.message : '未知错误'}`, '保存失败')
  } finally {
    savingChapterContent.value = false
  }
}

const handleGenerateOutline = async (numChapters: number) => {
  if (!project.value) return
  isGeneratingOutline.value = true
  try {
    const startChapter = (project.value.blueprint?.chapter_outline?.length || 0) + 1
    await novelStore.generateChapterOutline(startChapter, numChapters)
    globalAlert.showSuccess('新的章节大纲已生成', '操作成功')
  } catch (error) {
    console.error('生成大纲失败:', error)
    globalAlert.showError(`生成大纲失败: ${error instanceof Error ? error.message : '未知错误'}`, '生成失败')
  } finally {
    isGeneratingOutline.value = false
  }
}

onMounted(() => {
  loadProject()
  loadWritingModelOptions()
})
</script>

<style scoped>
/* 自定义样式 */
.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 自定义滚动条 */
::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: #a1a1a1;
}

/* 动画效果 */
.fade-in {
  animation: fadeIn 0.6s ease-out;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
