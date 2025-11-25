<template>
  <div class="vector-admin space-y-6">
    <n-card :bordered="false" class="overview-card frost-card" v-if="overview">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="text-lg font-semibold text-slate-800">向量库概览</span>
          <n-button size="small" secondary :loading="loadingProjects" @click="fetchProjects">刷新</n-button>
        </div>
      </template>
      <n-grid :cols="4" :x-gap="12" class="mt-2 stats-grid">
        <n-gi>
          <div class="stat-card-modern">
            <div class="stat-icon">📁</div>
            <n-statistic label="项目数" :value="overview.projectCount" />
          </div>
        </n-gi>
        <n-gi>
          <div class="stat-card-modern">
            <div class="stat-icon">📖</div>
            <n-statistic label="总章节" :value="overview.totalChapters" />
          </div>
        </n-gi>
        <n-gi>
          <div class="stat-card-modern">
            <div class="stat-icon">✅</div>
            <n-statistic label="已入库章节" :value="overview.ingested" />
          </div>
        </n-gi>
        <n-gi>
          <div class="stat-card-modern">
            <div class="stat-icon">💾</div>
            <n-statistic label="向量库大小" :value="formatBytes(overview.vectorSize)" />
          </div>
        </n-gi>
      </n-grid>
    </n-card>

    <n-card :bordered="false" class="frost-card">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="text-lg font-semibold text-slate-800">项目列表</span>
        </div>
      </template>
      <n-data-table
        :columns="projectColumns"
        :data="projects"
        :loading="loadingProjects"
        :row-key="rowKeyProject"
        size="small"
      />
    </n-card>

    <n-card v-if="selectedProjectId" :bordered="false" class="frost-card">
      <template #header>
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="text-lg font-semibold text-slate-800">章节详情</span>
            <n-tag type="info">项目 {{ selectedProjectId }}</n-tag>
            <span v-if="chapterTotals" class="text-xs text-slate-500">
              共 {{ chapterTotals.total }} 章 · 已入库 {{ chapterTotals.ingested }} · 未入库 {{ chapterTotals.missing }} · 待更新 {{ chapterTotals.stale }}
            </span>
          </div>
          <n-space size="small">
            <n-button size="small" secondary @click="openRetrievalTester" :disabled="!selectedProjectId">检索测试</n-button>
            <n-button size="small" secondary :loading="loadingChapters" @click="fetchChapters">刷新</n-button>
          </n-space>
        </div>
      </template>
      <div class="mb-3 flex items-center justify-between">
        <n-space size="small">
          <n-button size="small" type="primary" :disabled="!canOperate" :loading="operating" @click="handleReingest">重建向量</n-button>
          <n-button size="small" type="error" :disabled="!canOperate" :loading="operating" @click="handleDelete">删除向量</n-button>
        </n-space>
        <span class="text-xs text-slate-500">已选择 {{ selectedChapterKeys.length }} 个章节</span>
      </div>
      <n-data-table
        :columns="chapterColumns"
        :data="chapters"
        :loading="loadingChapters"
        :row-key="rowKeyChapter"
        size="small"
        checkable
        :checked-row-keys="selectedChapterKeys"
        @update:checked-row-keys="keys => (selectedChapterKeys = keys as number[])"
      />
    </n-card>

    <n-card :bordered="false" class="frost-card">
      <template #header>
        <span class="text-lg font-semibold text-slate-800">操作日志</span>
      </template>
      <n-log :lines="logMessages" :rows="6" :loading="false" language="plaintext" />
    </n-card>

    <n-drawer v-model:show="detailDrawerVisible" :width="640" placement="right">
      <n-drawer-content>
        <template #header>
          <div class="flex items-center justify-between w-full">
            <span class="text-base font-semibold text-slate-800">章节向量详情</span>
            <span v-if="detailData" class="text-xs text-slate-500">章节 {{ detailData.chapter_number }}</span>
          </div>
        </template>
        <div v-if="detailLoading" class="py-6 text-center text-slate-500">加载中...</div>
        <div v-else-if="detailData" class="space-y-4">
          <div>
            <h3 class="font-semibold text-slate-700">切片 ({{ detailData.chunks.length }})</h3>
            <div v-if="detailData.chunks.length" class="space-y-3 mt-2 chunk-list">
              <div v-for="chunk in detailData.chunks" :key="chunk.chunk_index" class="rounded-lg border border-slate-200 p-3 bg-slate-50">
                <div class="flex items-center justify-between text-xs text-slate-500 mb-2">
                  <span>Chunk {{ chunk.chunk_index }} · 维度 {{ chunk.embedding_dim }}</span>
                  <span v-if="chunk.created_at">{{ formatDateTime(chunk.created_at) }}</span>
                </div>
                <p class="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{{ chunk.content }}</p>
              </div>
            </div>
            <n-empty v-else description="暂无切片" class="mt-2" />
          </div>
          <div>
            <h3 class="font-semibold text-slate-700">摘要向量</h3>
            <div v-if="detailData.summary" class="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              <div class="flex items-center justify-between text-xs text-amber-600 mb-1">
                <span>维度 {{ detailData.summary.embedding_dim }}</span>
                <span v-if="detailData.summary.created_at">{{ formatDateTime(detailData.summary.created_at) }}</span>
              </div>
              <div class="font-semibold">{{ detailData.summary.title }}</div>
              <p class="mt-1 whitespace-pre-wrap leading-relaxed">{{ detailData.summary.summary }}</p>
            </div>
            <n-empty v-else description="暂无摘要向量" class="mt-2" />
          </div>
        </div>
        <n-empty v-else description="暂无数据" />
      </n-drawer-content>
    </n-drawer>

    <n-modal v-model:show="retrievalModalVisible" preset="dialog" title="向量检索测试" style="width: 520px">
      <n-form :model="retrievalForm" label-placement="top" class="space-y-2">
        <n-form-item label="检索文本">
          <n-input
            v-model:value="retrievalForm.query"
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 6 }"
            placeholder="请输入要检索的内容，例如章节摘要或关键词"
          />
        </n-form-item>
        <n-grid :cols="2" :x-gap="12">
          <n-gi>
            <n-form-item label="Chunk 数量">
              <n-input-number v-model:value="retrievalForm.top_k_chunks" :min="1" :max="20" />
            </n-form-item>
          </n-gi>
          <n-gi>
            <n-form-item label="摘要数量">
              <n-input-number v-model:value="retrievalForm.top_k_summaries" :min="0" :max="10" />
            </n-form-item>
          </n-gi>
        </n-grid>
      </n-form>
      <template #action>
        <n-space align="center" justify="end">
          <n-button @click="retrievalModalVisible = false" :disabled="retrievalLoading">取消</n-button>
          <n-button type="primary" :loading="retrievalLoading" @click="submitRetrieval">开始检索</n-button>
        </n-space>
      </template>
      <div v-if="retrievalResult" class="mt-4 space-y-4">
        <div>
          <h3 class="text-sm font-semibold text-slate-700">Chunk 结果 ({{ retrievalResult.chunks.length }})</h3>
          <div v-if="retrievalResult.chunks.length" class="mt-2 space-y-2">
            <div
              v-for="item in retrievalResult.chunks"
              :key="`${item.chapter_number}-${item.chunk_index}`"
              class="rounded border border-slate-200 p-2 text-xs"
            >
              <div class="flex items-center justify-between text-slate-500 mb-1">
                <span>第 {{ item.chapter_number }} 章 · Chunk {{ item.chunk_index ?? '-' }}</span>
                <span>相似度 {{ formatScore(item.score) }}</span>
              </div>
              <p class="whitespace-pre-wrap text-slate-700 leading-relaxed">{{ item.content }}</p>
            </div>
          </div>
          <n-empty v-else description="暂无召回结果" />
        </div>
        <div>
          <h3 class="text-sm font-semibold text-slate-700">摘要结果 ({{ retrievalResult.summaries.length }})</h3>
          <div v-if="retrievalResult.summaries.length" class="mt-2 space-y-2">
            <div
              v-for="item in retrievalResult.summaries"
              :key="`summary-${item.chapter_number}`"
              class="rounded border border-emerald-200 bg-emerald-50 p-2 text-xs"
            >
              <div class="flex items-center justify-between text-emerald-600 mb-1">
                <span>第 {{ item.chapter_number }} 章 · {{ item.title }}</span>
                <span>相似度 {{ formatScore(item.score) }}</span>
              </div>
              <p class="text-emerald-900 whitespace-pre-wrap leading-relaxed">{{ item.summary }}</p>
            </div>
          </div>
          <n-empty v-else description="暂无摘要召回" />
        </div>
      </div>
    </n-modal>
  </div>
</template>

<script setup lang="ts">
import { computed, h, onMounted, reactive, ref } from 'vue'
import type { DataTableColumns } from 'naive-ui'
import {
  NButton,
  NTag,
  NCard,
  NStatistic,
  NGrid,
  NGi,
  NDataTable,
  NDrawer,
  NDrawerContent,
  NLog,
  NEmpty,
  NForm,
  NFormItem,
  NInputNumber,
  NInput,
  NModal,
  NSpace
} from 'naive-ui'

import {
  VectorAPI,
  type VectorChapterDetailResponse,
  type VectorChapterListResponse,
  type VectorChapterSummary,
  type VectorProjectListResponse,
  type VectorProjectSummary,
  type VectorRetrievalTestRequest,
  type VectorRetrievalTestResponse
} from '@/api/vector'

import { useAlert } from '@/composables/useAlert'

const { showAlert } = useAlert()

const loadingProjects = ref(false)
const projectResponse = ref<VectorProjectListResponse | null>(null)
const selectedProjectId = ref<string | null>(null)
const loadingChapters = ref(false)
const chapterResponse = ref<VectorChapterListResponse | null>(null)
const operating = ref(false)

const detailDrawerVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref<VectorChapterDetailResponse | null>(null)

const retrievalModalVisible = ref(false)
const retrievalLoading = ref(false)
const retrievalForm = reactive<VectorRetrievalTestRequest>({
  query: '',
  top_k_chunks: 5,
  top_k_summaries: 3
})
const retrievalResult = ref<VectorRetrievalTestResponse | null>(null)

const logMessages = ref<string[]>([])

const selectedChapterKeys = ref<number[]>([])

const statusMap: Record<string, { label: string; type: 'success' | 'info' | 'warning' | 'error' | 'default' }> = {
  ingested: { label: '已入库', type: 'success' },
  partial: { label: '部分入库', type: 'warning' },
  missing: { label: '未入库', type: 'default' },
  stale: { label: '需更新', type: 'error' }
}

const overview = computed(() => {
  if (!projectResponse.value) return null
  const projects = projectResponse.value.projects
  const projectCount = projects.length
  let totalChapters = 0
  let ingested = 0
  let missing = 0
  let stale = 0
  for (const project of projects) {
    totalChapters += project.total_chapters
    ingested += project.ingested_chapters
    missing += project.missing_chapters
    stale += project.stale_chapters
  }
  return {
    projectCount,
    totalChapters,
    ingested,
    missing,
    stale,
    vectorSize: projectResponse.value.vector_db_size_bytes ?? 0
  }
})

const projects = computed<VectorProjectSummary[]>(() => projectResponse.value?.projects ?? [])
const chapters = computed<VectorChapterSummary[]>(() => chapterResponse.value?.chapters ?? [])
const chapterTotals = computed(() => chapterResponse.value?.totals ?? null)

const canOperate = computed(() => Boolean(selectedProjectId.value && selectedChapterKeys.value.length > 0 && !operating.value))

const projectColumns: DataTableColumns<VectorProjectSummary> = [
  {
    title: '项目',
    key: 'title',
    ellipsis: true,
    render(row) {
      return row.title || row.project_id
    }
  },
  { title: 'ID', key: 'project_id', ellipsis: true },
  { title: '总章节', key: 'total_chapters' },
  { title: '已入库', key: 'ingested_chapters' },
  { title: '未入库', key: 'missing_chapters' },
  { title: '待更新', key: 'stale_chapters' },
  {
    title: '最近入库',
    key: 'last_ingested_at',
    render(row) {
      return row.last_ingested_at ? formatDateTime(row.last_ingested_at) : '—'
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    render(row) {
      return h(
        NButton,
        {
          size: 'small',
          type: 'primary',
          quaternary: true,
          onClick: () => selectProject(row.project_id)
        },
        { default: () => '查看章节' }
      )
    }
  }
]

const chapterColumns: DataTableColumns<VectorChapterSummary> = [
  { type: 'selection' },
  { title: '章节号', key: 'chapter_number', width: 90 },
  { title: '标题', key: 'title', ellipsis: true },
  {
    title: '状态',
    key: 'status',
    width: 110,
    render(row) {
      const info = statusMap[row.status] || statusMap.missing
      return h(
        NTag,
        { type: info.type, size: 'small', bordered: false },
        { default: () => info.label }
      )
    }
  },
  { title: 'Chunks', key: 'chunk_count', width: 90 },
  { title: '摘要', key: 'summary_count', width: 90 },
  {
    title: '入库时间',
    key: 'last_ingested_at',
    render(row) {
      return row.last_ingested_at ? formatDateTime(row.last_ingested_at) : '—'
    }
  },
  {
    title: '确认状态',
    key: 'confirmed',
    width: 110,
    render(row) {
      return row.confirmed
        ? h(NTag, { type: 'success', size: 'small', bordered: false }, { default: () => '已确认' })
        : h(NTag, { type: 'default', size: 'small', bordered: false }, { default: () => '未确认' })
    }
  },
  {
    title: '操作',
    key: 'action',
    width: 120,
    render(row) {
      return h(
        NButton,
        {
          size: 'small',
          tertiary: true,
          onClick: () => openChapterDetail(row.chapter_number)
        },
        { default: () => '查看详情' }
      )
    }
  }
]

function rowKeyProject(row: VectorProjectSummary) {
  return row.project_id
}

function rowKeyChapter(row: VectorChapterSummary) {
  return row.chapter_number
}

function formatDateTime(value?: string | null): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`
}

function formatBytes(size?: number | null): string {
  if (!size || size <= 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let index = 0
  let value = size
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024
    index++
  }
  return `${value.toFixed(2)}\u00a0${units[index]}`
}

function formatScore(score: number): string {
  if (!Number.isFinite(score)) return '—'
  return score.toFixed(4)
}

function pushLog(messageText: string) {
  const timestamp = new Date().toLocaleTimeString()
  logMessages.value = [`[${timestamp}] ${messageText}`, ...logMessages.value].slice(0, 100)
}

async function fetchProjects() {
  loadingProjects.value = true
  try {
    projectResponse.value = await VectorAPI.getProjects()
    pushLog('已刷新项目列表')
    const ids = new Set(projectResponse.value.projects.map(item => item.project_id))
    if (selectedProjectId.value && !ids.has(selectedProjectId.value)) {
      selectedProjectId.value = null
      chapterResponse.value = null
    }
    if (!selectedProjectId.value && projectResponse.value.projects.length) {
      selectProject(projectResponse.value.projects[0].project_id)
    }
  } catch (error) {
    showAlert((error as Error).message, 'error')
    pushLog(`刷新项目列表失败：${(error as Error).message}`)
  } finally {
    loadingProjects.value = false
  }
}

async function fetchChapters() {
  if (!selectedProjectId.value) return
  loadingChapters.value = true
  try {
    chapterResponse.value = await VectorAPI.getProjectChapters(selectedProjectId.value)
    selectedChapterKeys.value = []
    pushLog(`已获取项目 ${selectedProjectId.value} 的章节列表`)
  } catch (error) {
    showAlert((error as Error).message, 'error')
    pushLog(`获取章节列表失败：${(error as Error).message}`)
  } finally {
    loadingChapters.value = false
  }
}

function selectProject(projectId: string) {
  if (selectedProjectId.value === projectId) return
  selectedProjectId.value = projectId
  chapterResponse.value = null
  selectedChapterKeys.value = []
  fetchChapters()
}

async function handleReingest() {
  if (!selectedProjectId.value || selectedChapterKeys.value.length === 0 || operating.value) return
  operating.value = true
  try {
    const result = await VectorAPI.reingest(selectedProjectId.value, selectedChapterKeys.value)
    if (result) {
      const summary = `重建成功 ${result.processed} 条，跳过 ${result.skipped} 条，失败 ${result.failed} 条`
      showAlert(summary, result.failed > 0 ? 'error' : 'success')
      if (result.message) pushLog(result.message)
      pushLog(`重建完成：${summary}`)
    }
    await fetchChapters()
  } catch (error) {
    showAlert((error as Error).message, 'error')
    pushLog(`重建向量失败：${(error as Error).message}`)
  } finally {
    operating.value = false
  }
}

async function handleDelete() {
  if (!selectedProjectId.value || selectedChapterKeys.value.length === 0 || operating.value) return
  const confirmed = await showAlert(
    `即将删除 ${selectedChapterKeys.value.length} 个章节的向量数据，操作不可恢复，确认继续吗？`,
    'confirmation',
    '确认删除',
    { showCancel: true }
  )
  if (!confirmed) return
  operating.value = true
  try {
    const result = await VectorAPI.delete(selectedProjectId.value!, selectedChapterKeys.value)
    if (result) {
      showAlert(`已删除 ${result.processed} 个章节的向量数据`, 'success')
      pushLog(`删除向量：章节 ${selectedChapterKeys.value.join(', ')}`)
    }
    await fetchChapters()
  } catch (error) {
    showAlert((error as Error).message, 'error')
    pushLog(`删除向量失败：${(error as Error).message}`)
  } finally {
    operating.value = false
  }
}

async function openChapterDetail(chapterNumber: number) {
  if (!selectedProjectId.value) return
  detailDrawerVisible.value = true
  detailLoading.value = true
  detailData.value = null
  try {
    detailData.value = await VectorAPI.getChapterDetail(selectedProjectId.value, chapterNumber)
  } catch (error) {
    showAlert((error as Error).message, 'error')
    pushLog(`获取章节详情失败：${(error as Error).message}`)
  } finally {
    detailLoading.value = false
  }
}

function openRetrievalTester() {
  if (!selectedProjectId.value) return
  retrievalModalVisible.value = true
  retrievalResult.value = null
  retrievalForm.query = ''
}

async function submitRetrieval() {
  if (!selectedProjectId.value || !retrievalForm.query.trim()) {
    showAlert('请输入检索文本', 'info')
    return
  }
  retrievalLoading.value = true
  try {
    retrievalResult.value = await VectorAPI.testRetrieval(selectedProjectId.value, {
      query: retrievalForm.query,
      top_k_chunks: retrievalForm.top_k_chunks,
      top_k_summaries: retrievalForm.top_k_summaries
    })
    const chunkCount = retrievalResult.value?.chunks?.length ?? 0
    pushLog(`完成检索测试，返回 ${chunkCount} 个 chunk`)
  } catch (error) {
    showAlert((error as Error).message, 'error')
    pushLog(`检索失败：${(error as Error).message}`)
  } finally {
    retrievalLoading.value = false
  }
}

onMounted(() => {
  fetchProjects()
})
</script>

<style scoped>
.vector-admin {
  display: flex;
  flex-direction: column;
}
.frost-card {
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(18px);
  border-radius: 1.5rem;
  box-shadow: 0 20px 45px rgba(15, 23, 42, 0.12);
  border: none;
  overflow: hidden;
}
.frost-card :deep(.n-card__border) {
  display: none;
}
.frost-card :deep(.n-card__content) {
  padding: 20px 28px 28px;
}
.frost-card :deep(.n-card__header) {
  padding: 24px 28px 10px;
  background: transparent;
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
}
.overview-card :deep(.n-card__content) {
  padding-top: 16px;
}
.stats-grid {
  width: 100%;
}
.stat-card-modern {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 12px 16px;
  transition: all 0.2s ease;
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
}
.stat-card-modern:hover {
  border-color: #cbd5e1;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
}
.stat-icon {
  font-size: 1.75rem;
  line-height: 1;
  flex-shrink: 0;
  opacity: 0.85;
}
.stat-card-modern:nth-child(1)::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: #667eea;
  border-radius: 8px 0 0 8px;
}
.stat-card-modern:nth-child(2)::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: #f59e0b;
  border-radius: 8px 0 0 8px;
}
.stat-card-modern:nth-child(3)::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: #10b981;
  border-radius: 8px 0 0 8px;
}
.stat-card-modern:nth-child(4)::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  background: #06b6d4;
  border-radius: 8px 0 0 8px;
}
.stat-card-modern :deep(.n-statistic) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.stat-card-modern :deep(.n-statistic-value) {
  font-size: 1.5rem;
  font-weight: 700;
  color: #1e293b;
  line-height: 1;
  white-space: nowrap;
}
.stat-card-modern :deep(.n-statistic-label) {
  font-size: 0.8125rem;
  font-weight: 500;
  color: #64748b;
  text-transform: none;
  line-height: 1.2;
}
.chunk-list {
  max-height: 360px;
  overflow-y: auto;
}
</style>
