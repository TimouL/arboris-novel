<template>
  <div class="writing-model-avatar-list flex items-center gap-4 w-full py-0">
    <div
      v-for="model in models"
      :key="model.key"
      class="avatar-card flex-shrink-0 relative group"
    >
      <button
        type="button"
        class="avatar-button group relative flex flex-col items-center"
        :class="{
          'cursor-pointer': model.canToggle || (model.canStop && isGeneratingStatus(model.status)),
          'cursor-not-allowed': !model.canToggle && !model.canStop && !isGeneratingStatus(model.status)
        }"
        @click="handleClick(model)"
      >
        <div
          class="avatar-circle relative flex items-center justify-center"
          :class="{
            'avatar-active': model.selected,
            'avatar-disabled': !model.selected
          }"
        >
          <svg
            class="avatar-illustration"
            viewBox="0 0 64 64"
            role="img"
            aria-hidden="true"
          >
            <circle
              cx="32"
              cy="32"
              r="30"
              :fill="avatarArtwork(model.key).bg"
            />
            <path
              d="M32 20c7.2 0 12 5.3 12 13.2 0 7.9-4.8 13.2-12 13.2s-12-5.3-12-13.2C20 25.3 24.8 20 32 20z"
              :fill="avatarArtwork(model.key).skin"
            />
            <path
              d="M20.5 30.5c1.6-8 7-12.5 11.6-12.5 4.6 0 9.7 4.3 11.4 11.8 0.3 1.1-0.5 2.2-1.6 2.2H22.1c-1.1 0-1.9-1.1-1.6-2.2z"
              :fill="avatarArtwork(model.key).hair"
            />
            <circle
              cx="26"
              cy="34"
              r="1.8"
              :fill="avatarArtwork(model.key).eye"
            />
            <circle
              cx="38"
              cy="34"
              r="1.8"
              :fill="avatarArtwork(model.key).eye"
            />
            <path
              d="M27 41c1.6 1.8 3.3 2.7 5 2.7s3.4-0.9 5-2.7"
              :stroke="avatarArtwork(model.key).mouth"
              stroke-width="2"
              stroke-linecap="round"
              fill="none"
            />
            <circle
              cx="24"
              cy="38"
              r="1.4"
              :fill="avatarArtwork(model.key).cheek"
            />
            <circle
              cx="40"
              cy="38"
              r="1.4"
              :fill="avatarArtwork(model.key).cheek"
            />
            <path
              d="M32 52c-7.1 0-12-2.8-14.6-5.1-.8-.8-.2-2.2 0.9-2.2h27.4c1.1 0 1.7 1.3 0.9 2.2C44 49.2 39.1 52 32 52z"
              :fill="avatarArtwork(model.key).outfit"
            />
          </svg>
          <span
            v-if="model.isPrimary"
            class="absolute -top-0 -right-1.5 inline-flex items-center justify-center rounded-full bg-amber-500 text-white text-[10px] font-bold px-1.5 py-[1px] shadow"
          >
            主
          </span>
          <button
            v-if="progressBadge(model)"
            type="button"
            class="progress-badge"
            :class="model.isPrimary ? 'badge-primary' : ''"
            :data-model-badge="model.key"
            :title="badgeTooltip(model)"
            :disabled="isGeneratingStatus(model.status) || props.updatingKey === model.key"
            @mousedown.stop
            @click.stop="openVariantEditor(model)"
          >
            <span v-if="props.updatingKey === model.key" class="inline-flex items-center justify-center">
              <svg class="w-3.5 h-3.5 animate-spin text-white/80" viewBox="0 0 20 20" fill="none">
                <path
                  d="M10 3v1.5M15.303 4.697l-1.06 1.06M17 10h-1.5M15.303 15.303l-1.06-1.06M10 15.5V17M5.757 14.243l-1.06 1.06M4.5 10H3M5.757 5.757l-1.06-1.06"
                  stroke="currentColor"
                  stroke-width="1.4"
                  stroke-linecap="round"
                />
              </svg>
            </span>
            <span v-else>{{ progressBadge(model) }}</span>
          </button>
          <span
            v-if="isGeneratingStatus(model.status) && model.canStop"
            class="absolute inset-0 rounded-full border-2 border-white/60"
          ></span>
        </div>
        <span class="mt-1 text-[11px] font-medium text-slate-700 max-w-[70px] text-center line-clamp-1">
          {{ model.displayName }}
        </span>
        <span class="text-[10px] text-slate-500 max-w-[70px] text-center line-clamp-1">
          {{ statusLine(model) }}
        </span>
      </button>
      <button
        v-if="isGeneratingStatus(model.status) && model.canStop"
        type="button"
        class="stop-button absolute -top-1 -right-1 hidden h-5 w-5 items-center justify-center rounded-full bg-white text-rose-500 shadow group-hover:flex"
        @click.stop="emitStop(model.key)"
      >
        ✕
      </button>
    </div>
  </div>
  <Teleport to="body">
    <div
      v-if="variantEditor.visible"
      ref="variantEditorRef"
      class="variant-editor global-overlay"
      :style="variantEditorPosition"
    >
      <div class="variant-editor-content">
        <p class="variant-editor-title">生成版本数</p>
        <div class="variant-editor-controls">
          <div class="variant-editor-stepper">
            <button
              type="button"
              class="stepper-btn"
              :disabled="variantEditor.value <= MIN_VARIANTS || props.updatingKey === variantEditor.modelKey"
              @click="adjustVariants(-1)"
            >
              -
            </button>
            <input
              ref="variantInputRef"
              v-model.number="variantEditor.value"
              type="number"
              :min="MIN_VARIANTS"
              :max="MAX_VARIANTS"
              class="stepper-input"
              :disabled="props.updatingKey === variantEditor.modelKey"
              @keydown.stop
              @keydown.enter.prevent="applyVariantEditor"
            >
            <button
              type="button"
              class="stepper-btn"
              :disabled="variantEditor.value >= MAX_VARIANTS || props.updatingKey === variantEditor.modelKey"
              @click="adjustVariants(1)"
            >
              +
            </button>
          </div>
          <button
            type="button"
            class="variant-editor-confirm"
            :disabled="props.updatingKey === variantEditor.modelKey"
            @click="applyVariantEditor"
          >
            {{ props.updatingKey === variantEditor.modelKey ? '保存中…' : '应用' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { Teleport, computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import type { WritingModelAvatarItem, WritingModelAvatarStatus } from './modelAvatarTypes'

const props = defineProps<{
  models: WritingModelAvatarItem[]
  updatingKey?: string | null
}>()

const emit = defineEmits<{
  (e: 'toggle', modelKey: string): void
  (e: 'stop', modelKey: string): void
  (e: 'updateVariants', payload: { modelKey: string; variants: number }): void
}>()

const nowTick = ref(Date.now())
let timer: number | null = null

const hasActiveTimer = computed(() =>
  props.models.some(model => isGeneratingStatus(model.status) && model.startedAt !== null)
)

const startTimer = () => {
  if (timer !== null) return
  timer = window.setInterval(() => {
    nowTick.value = Date.now()
  }, 1000)
}

const stopTimer = () => {
  if (timer !== null) {
    clearInterval(timer)
    timer = null
  }
}

onMounted(() => {
  if (hasActiveTimer.value) {
    startTimer()
  }
  if (typeof window !== 'undefined') {
    document.addEventListener('mousedown', handleDocumentClick)
    document.addEventListener('keydown', handleEscapeKey)
  }
})

onBeforeUnmount(() => {
  stopTimer()
  if (typeof window !== 'undefined') {
    document.removeEventListener('mousedown', handleDocumentClick)
    document.removeEventListener('keydown', handleEscapeKey)
  }
})

const formatDuration = (model: WritingModelAvatarItem) => {
  if (!model.startedAt) return ''
  const end = model.finishedAt ?? nowTick.value
  const ms = Math.max(end - model.startedAt, 0)
  const totalSeconds = Math.floor(ms / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  const mm = minutes.toString().padStart(2, '0')
  const ss = seconds.toString().padStart(2, '0')
  return `${mm}:${ss}`
}

const statusLine = (model: WritingModelAvatarItem) => {
  if (!model.selected && !isGeneratingStatus(model.status)) {
    return '禁用'
  }
  switch (model.status) {
    case 'generating':
      return formatDuration(model) || '00:00'
    case 'stopping':
      return '停止中'
    case 'queued':
      return '排队中'
    case 'completed': {
      const duration = formatDuration(model)
      return duration ? `完成 · ${duration}` : '完成'
    }
    case 'stopped':
      return model.currentVariant > 0 ? '已停止' : '已停止'
    case 'error':
      return model.errorMessage ? `失败 · ${model.errorMessage}` : '生成失败'
    case 'selected':
      return '待命'
    default:
      return '待命'
  }
}

const progressBadge = (model: WritingModelAvatarItem) => {
  if (!model.selected && !isGeneratingStatus(model.status)) {
    return null
  }
  const total = Math.max(model.targetVariants, 1)
  const current = Math.min(model.currentVariant, total)
  return `${current}/${total}`
}

const badgeTooltip = (model: WritingModelAvatarItem) => {
  if (isGeneratingStatus(model.status)) {
    return '生成中，暂不可调整'
  }
  return '点击修改生成版本数'
}

const MIN_VARIANTS = 1
const MAX_VARIANTS = 10

const clampVariants = (value: number) => {
  if (Number.isNaN(value)) {
    return MIN_VARIANTS
  }
  return Math.max(MIN_VARIANTS, Math.min(Math.round(value), MAX_VARIANTS))
}

const variantEditor = reactive({
  visible: false,
  modelKey: '',
  value: MIN_VARIANTS,
  anchorRect: null as DOMRect | null
})

const variantEditorRef = ref<HTMLElement | null>(null)
const variantInputRef = ref<HTMLInputElement | null>(null)

const variantEditorPosition = computed(() => {
  if (!variantEditor.visible || !variantEditor.anchorRect) {
    return {}
  }
  const anchor = variantEditor.anchorRect
  const defaultWidth = Math.max(anchor.width + 80, 200)
  const editorWidth = variantEditorRef.value?.offsetWidth ?? defaultWidth
  const editorHeight = variantEditorRef.value?.offsetHeight ?? 120
  const viewportWidth = typeof window !== 'undefined' ? window.innerWidth : 0
  const viewportHeight = typeof window !== 'undefined' ? window.innerHeight : 0

  let left = anchor.left + anchor.width + 12
  let top = anchor.top

  if (left + editorWidth > viewportWidth - 16) {
    left = Math.max(16, anchor.left + anchor.width / 2 - editorWidth / 2)
  }
  if (top + editorHeight > viewportHeight - 16) {
    top = Math.max(16, viewportHeight - editorHeight - 16)
  }

  return {
    left: `${left}px`,
    top: `${top}px`
  }
})

const openVariantEditor = (model: WritingModelAvatarItem) => {
  if (isGeneratingStatus(model.status)) {
    return
  }
  if (typeof document !== 'undefined') {
    const badgeElement = document.querySelector<HTMLButtonElement>(
      `[data-model-badge="${model.key}"]`
    )
    variantEditor.anchorRect = badgeElement?.getBoundingClientRect() ?? null
  } else {
    variantEditor.anchorRect = null
  }
  variantEditor.visible = true
  variantEditor.modelKey = model.key
  variantEditor.value = clampVariants(model.targetVariants || MIN_VARIANTS)
  nextTick(() => {
    variantInputRef.value?.focus()
    variantInputRef.value?.select()
  })
}

const closeVariantEditor = () => {
  variantEditor.visible = false
  variantEditor.modelKey = ''
  variantEditor.anchorRect = null
}

const adjustVariants = (delta: number) => {
  variantEditor.value = clampVariants(variantEditor.value + delta)
}

const applyVariantEditor = () => {
  if (!variantEditor.modelKey) {
    return
  }
  const normalized = clampVariants(variantEditor.value)
  emit('updateVariants', { modelKey: variantEditor.modelKey, variants: normalized })
  closeVariantEditor()
}

const handleDocumentClick = (event: MouseEvent) => {
  if (!variantEditor.visible) {
    return
  }
  const target = event.target as Node | null
  if (
    variantEditorRef.value &&
    (variantEditorRef.value === target || variantEditorRef.value.contains(target))
  ) {
    return
  }
  closeVariantEditor()
}

const handleEscapeKey = (event: KeyboardEvent) => {
  if (!variantEditor.visible) {
    return
  }
  if (event.key === 'Escape') {
    closeVariantEditor()
  }
}

const isGeneratingStatus = (status: WritingModelAvatarStatus) =>
  status === 'generating' || status === 'stopping'

const handleClick = (model: WritingModelAvatarItem) => {
  if (isGeneratingStatus(model.status)) {
    if (model.canStop) {
      emitStop(model.key)
    }
    return
  }
  if (model.canToggle) {
    emit('toggle', model.key)
  }
}

const emitStop = (modelKey: string) => {
  emit('stop', modelKey)
}

interface CartoonAvatar {
  bg: string
  skin: string
  hair: string
  eye: string
  cheek: string
  mouth: string
  outfit: string
}

const cartoonAvatars: CartoonAvatar[] = [
  { bg: '#FDE68A', skin: '#FBD6C4', hair: '#1F2937', eye: '#1F2937', cheek: '#FCA5A5', mouth: '#EC4899', outfit: '#4C1D95' },
  { bg: '#BFDBFE', skin: '#FFE4CC', hair: '#7C3AED', eye: '#1F2937', cheek: '#F9A8D4', mouth: '#9333EA', outfit: '#1D4ED8' },
  { bg: '#FBCFE8', skin: '#FCE1BE', hair: '#EA580C', eye: '#1F2937', cheek: '#FCA5A5', mouth: '#EA580C', outfit: '#DB2777' },
  { bg: '#BBF7D0', skin: '#FFDFCC', hair: '#0F172A', eye: '#0F172A', cheek: '#FDBA74', mouth: '#2563EB', outfit: '#0EA5E9' },
  { bg: '#FCD34D', skin: '#FDD6BE', hair: '#1E3A8A', eye: '#1F2937', cheek: '#F87171', mouth: '#1E3A8A', outfit: '#F97316' },
  { bg: '#C4B5FD', skin: '#FFE2CC', hair: '#111827', eye: '#111827', cheek: '#FCA5A5', mouth: '#7C3AED', outfit: '#4338CA' }
]

const avatarArtwork = (key: string): CartoonAvatar => {
  const hash = key.split('').reduce((acc, ch) => acc + ch.charCodeAt(0), 0)
  return cartoonAvatars[hash % cartoonAvatars.length]
}

watch(hasActiveTimer, (active) => {
  if (active) {
    startTimer()
  } else {
    stopTimer()
  }
}, { immediate: true })
</script>

<style scoped>
.writing-model-avatar-list {
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  width: 100%;
  overflow-x: auto;
  overflow-y: visible;
  scrollbar-width: thin;
  padding: 0;
  margin: 0;
}

.writing-model-avatar-list::-webkit-scrollbar {
  height: 0;
}

.avatar-card {
  width: 74px;
  padding-bottom: 6px;
}

.avatar-button {
  gap: 1px;
}

.avatar-circle {
  width: 60px;
  height: 60px;
  border-radius: 999px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  box-shadow: 0 4px 12px rgba(79, 70, 229, 0.12);
}

.avatar-button:hover .avatar-circle {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(79, 70, 229, 0.18);
}

.avatar-illustration {
  width: 54px;
  height: 54px;
}

.stop-button {
  font-size: 11px;
}

.avatar-active {
  border: 2px solid rgba(129, 140, 248, 0.4);
}

.avatar-disabled {
  filter: grayscale(100%);
  opacity: 0.55;
  border: 2px solid rgba(148, 163, 184, 0.35);
}

.progress-badge {
  position: absolute;
  top: 6px;
  right: -4px;
  transform: translateY(-50%);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  cursor: pointer;

  background: rgba(79, 70, 229, 0.92);
  color: #f8fafc;
  font-size: 9px;
  font-weight: 600;
  padding: 0 6px;
  border-radius: 999px;
  box-shadow: 0 4px 10px rgba(79, 70, 229, 0.2);
}

.badge-primary {
  top: auto;
  bottom: -6px;
  transform: none;
}

.progress-badge:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.animate-spin-slow {
  animation: spin 1.2s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.variant-editor {
  position: absolute;
  z-index: 40;
}

.variant-editor-content {
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid rgba(99, 102, 241, 0.16);
  box-shadow: 0 16px 32px rgba(15, 23, 42, 0.18);
  padding: 12px;
  display: inline-flex;
  flex-direction: column;
}

.variant-editor-controls {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 12px;
  flex-wrap: wrap;
  width: max-content;
}

.variant-editor-title {
  font-size: 12px;
  font-weight: 600;
  color: #4338ca;
  margin-bottom: 8px;
}

.variant-editor-stepper {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.stepper-btn {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  border: 1px solid rgba(99, 102, 241, 0.2);
  background: rgba(99, 102, 241, 0.08);
  color: #3730a3;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s ease;
}

.stepper-btn:hover:not(:disabled) {
  background: rgba(99, 102, 241, 0.18);
}

.stepper-btn:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.stepper-input {
  width: 56px;
  height: 28px;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.5);
  text-align: center;
  font-size: 13px;
  padding: 0;
}

.variant-editor-confirm {
  font-size: 12px;
  padding: 6px 14px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  transition: background 0.2s ease;
  min-width: 64px;
  background: #4f46e5;
  color: #ffffff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.variant-editor-confirm:hover:not(:disabled) {
  background: #4338ca;
}

.variant-editor-confirm:disabled,
.stepper-input:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
</style>
