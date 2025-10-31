<template>
  <div class="bg-white/70 backdrop-blur-xl rounded-2xl shadow-lg p-8 space-y-8">
    <header class="space-y-2">
      <h2 class="text-2xl font-bold text-gray-800">写作模型管理</h2>
      <p class="text-sm text-gray-600">配置参与章节写作的附加模型，主模型依旧由 LLM 配置控制。</p>
    </header>

    <div class="flex items-center justify-between bg-indigo-50 border border-indigo-100 rounded-xl p-4">
      <div>
        <h3 class="text-lg font-semibold text-indigo-800">多模型写作</h3>
        <p class="text-sm text-indigo-600">开启后，所选附加模型将在生成章节时与主模型一同调用。</p>
      </div>
      <label class="inline-flex items-center cursor-pointer">
        <input type="checkbox" class="sr-only" v-model="localSettings.enabled">
        <span class="w-14 h-8 bg-gray-200 rounded-full transition" :class="localSettings.enabled ? 'bg-indigo-500' : 'bg-gray-200'"></span>
        <span class="ml-3 text-sm text-gray-700">{{ localSettings.enabled ? '已启用' : '已关闭' }}</span>
      </label>
    </div>

    <div class="grid md:grid-cols-2 gap-4">
      <label class="block">
        <span class="text-sm font-medium text-gray-700">每模型默认生成版本数</span>
        <input
          type="number"
          min="1"
          max="10"
          v-model.number="localSettings.fallback_variants"
          class="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"
        >
      </label>
    </div>

    <div class="space-y-4">
      <div class="flex items-center justify-between">
        <h3 class="text-lg font-semibold text-gray-800">附加模型列表</h3>
        <button
          type="button"
          class="px-3 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700"
          @click="addModel"
        >
          + 新增模型
        </button>
      </div>

      <div v-if="localSettings.models.length === 0" class="text-sm text-gray-500 bg-gray-50 border border-dashed border-gray-200 rounded-lg p-6 text-center">
        暂无附加模型，点击“新增模型”即可添加。
      </div>

      <div
        v-for="(model, index) in localSettings.models"
        :key="model.key"
        class="border border-gray-200 rounded-xl p-4 space-y-4 bg-white"
      >
        <div class="flex items-center justify-between">
          <h4 class="text-base font-semibold text-gray-800">模型 {{ index + 1 }}</h4>
          <div class="flex items-center gap-3">
            <label class="flex items-center gap-1 text-sm text-gray-600">
              <input type="checkbox" v-model="model.enabled">
              启用
            </label>
            <button
              type="button"
              class="text-sm text-red-500 hover:text-red-600"
              @click="removeModel(index)"
            >删除</button>
          </div>
        </div>

        <div class="grid md:grid-cols-2 gap-4">
          <label class="block text-sm">
            <span class="text-gray-700">标识 key</span>
            <input v-model.trim="model.key" class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500" placeholder="如 claude-sonnet">
          </label>
          <label class="block text-sm">
            <span class="text-gray-700">显示名称</span>
            <input v-model.trim="model.display_name" class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500" placeholder="如 Claude 3.5 Sonnet">
          </label>
          <label class="block text-sm">
            <span class="text-gray-700">提供商</span>
            <input v-model.trim="model.provider" class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500" placeholder="OpenAI / Anthropic 等">
          </label>
          <label class="block text-sm">
            <span class="text-gray-700">模型 ID</span>
            <input v-model.trim="model.model" class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500" placeholder="如 claude-3-5-sonnet">
          </label>
          <label class="block text-sm">
            <span class="text-gray-700">Base URL（可选）</span>
            <input v-model.trim="model.base_url" class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500" placeholder="https://...">
          </label>
          <label class="block text-sm">
            <span class="text-gray-700">专用 API Key（可选）</span>
            <input v-model.trim="model.api_key" class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500" placeholder="若为空则复用主 API Key">
          </label>
          <label class="block text-sm">
            <span class="text-gray-700">Temperature</span>
            <input type="number" step="0.05" min="0" max="2" v-model.number="model.temperature" class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500">
          </label>
          <label class="block text-sm">
            <span class="text-gray-700">生成版本数</span>
            <input type="number" min="1" max="10" v-model.number="model.variants" class="mt-1 w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500">
          </label>
        </div>
      </div>
    </div>

    <div class="flex justify-end gap-4 pt-4">
      <button
        type="button"
        class="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
        @click="reset"
        :disabled="loading || saving"
      >重置</button>
      <button
        type="button"
        class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
        @click="save"
        :disabled="saving"
      >{{ saving ? '保存中...' : '保存设置' }}</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { AdminAPI, type WritingModelSettings, type WritingModelConfig } from '@/api/admin'

const loading = ref(false)
const saving = ref(false)
const localSettings = reactive<WritingModelSettings>({
  enabled: false,
  fallback_variants: 3,
  models: []
})

const snapshot = ref<WritingModelSettings | null>(null)

const loadSettings = async () => {
  try {
    loading.value = true
    const settings = await AdminAPI.getWritingModelSettings()
    applySettings(settings)
    snapshot.value = JSON.parse(JSON.stringify(settings))
  } catch (error) {
    console.error('加载写作模型配置失败', error)
  } finally {
    loading.value = false
  }
}

const applySettings = (settings: WritingModelSettings) => {
  localSettings.enabled = settings.enabled
  localSettings.fallback_variants = settings.fallback_variants
  localSettings.models = settings.models.map(model => ({ ...model }))
}

const addModel = () => {
  const suffix = localSettings.models.length + 1
  const newModel: WritingModelConfig = {
    key: `model-${suffix}`,
    display_name: `模型 ${suffix}`,
    provider: '',
    model: '',
    base_url: '',
    api_key: '',
    temperature: 0.9,
    variants: 2,
    enabled: true
  }
  localSettings.models.push(newModel)
}

const removeModel = (index: number) => {
  localSettings.models.splice(index, 1)
}

const reset = () => {
  if (snapshot.value) {
    applySettings(snapshot.value)
  }
}

const save = async () => {
  try {
    saving.value = true
    const payload: WritingModelSettings = {
      enabled: localSettings.enabled,
      fallback_variants: Math.max(1, localSettings.fallback_variants || 1),
      models: localSettings.models.map(model => ({
        ...model,
        variants: Math.max(1, model.variants || 1),
        temperature: typeof model.temperature === 'number' ? model.temperature : 0.9,
        base_url: model.base_url || '',
        api_key: model.api_key || ''
      }))
    }
    const updated = await AdminAPI.updateWritingModelSettings(payload)
    applySettings(updated)
    snapshot.value = JSON.parse(JSON.stringify(updated))
    alert('写作模型配置已保存！')
  } catch (error: any) {
    alert(error?.message || '保存失败，请稍后重试')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadSettings()
})
</script>
