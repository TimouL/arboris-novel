<template>
  <div class="inline-flex items-center gap-2 flex-wrap">
    <button
      class="inline-flex items-center gap-1 px-3 py-1 text-xs font-medium rounded-full border"
      :class="['border-green-200 text-green-700 bg-green-50 hover:bg-green-100', disabled ? 'opacity-60 cursor-not-allowed' : '']"
      :disabled="disabled"
      @click="$emit('run')"
    >
      <slot name="icon">
        <svg v-if="!loading" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
        <svg v-else class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path>
        </svg>
      </slot>
      <span>{{ loading ? '检测中' : 'AI检测' }}</span>
    </button>
    <div v-if="showResult" class="inline-flex items-center gap-2 text-xs px-2.5 py-1 rounded-full border border-emerald-200 bg-emerald-50 text-emerald-700">
      <span>AI检测</span>
      <span>{{ confidence }}% AI</span>
    </div>
  </div>

  <div v-if="showResult" class="w-full max-w-xl flex items-center gap-3 mt-2">
    <div class="flex-1 h-2 rounded-full bg-gray-100 overflow-hidden flex">
      <div class="h-full bg-emerald-400" :style="{ width: breakdownMap[0] + '%' }"></div>
      <div class="h-full bg-amber-400" :style="{ width: breakdownMap[2] + '%' }"></div>
      <div class="h-full bg-red-400" :style="{ width: breakdownMap[1] + '%' }"></div>
    </div>
    <div class="flex items-center gap-2 text-xs text-gray-600 flex-wrap">
      <span class="text-emerald-700">人工 {{ breakdownMap[0] }}%</span>
      <span class="text-amber-700">疑似 {{ breakdownMap[2] }}%</span>
      <span class="text-red-700">AI {{ breakdownMap[1] }}%</span>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Props {
  disabled?: boolean
  loading?: boolean
  confidence?: string | number
  breakdownMap: Record<number, number>
  showResult?: boolean
}

defineProps<Props>()
defineEmits(['run'])
</script>
