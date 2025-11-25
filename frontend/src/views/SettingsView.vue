<template>
  <div class="min-h-screen p-4 relative">
    <div class="fixed top-4 left-4 z-50">
      <router-link
        to="/"
        class="px-4 py-2 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors flex items-center gap-2"
      >
        &larr; 返回
      </router-link>
    </div>
    <div class="max-w-6xl mx-auto mt-16">
      <div class="flex flex-col md:flex-row">
        <!-- Sidebar -->
        <div class="w-full md:w-64 mb-4 md:mb-0 md:mr-8">
          <div class="md:fixed md:w-64 md:min-h-[calc(100vh-6rem)] bg-white/70 backdrop-blur-xl rounded-2xl shadow-lg p-4">
            <h2 class="text-xl font-bold text-gray-800 mb-4">设置</h2>
            <nav>
              <ul class="space-y-2">
                <li
                  class="px-4 py-2 rounded-lg cursor-pointer transition"
                  :class="activeTab === 'llm' ? 'bg-indigo-100 text-indigo-700' : 'text-gray-600 hover:bg-gray-100'"
                  @click="activeTab = 'llm'"
                >
                  LLM 配置
                </li>
                <li
                  class="px-4 py-2 rounded-lg cursor-pointer transition"
                  :class="activeTab === 'writing' ? 'bg-indigo-100 text-indigo-700' : 'text-gray-600 hover:bg-gray-100'"
                  @click="activeTab = 'writing'"
                >
                  写作模型管理
                </li>
                <li
                  class="px-4 py-2 rounded-lg cursor-pointer transition"
                  :class="activeTab === 'vector' ? 'bg-indigo-100 text-indigo-700' : 'text-gray-600 hover:bg-gray-100'"
                  @click="activeTab = 'vector'"
                >
                  向量库管理
                </li>
              </ul>
            </nav>
          </div>
        </div>

        <!-- Main Content -->
        <div class="flex-1">
          <LLMSettings v-if="activeTab === 'llm'" />
          <WritingModelSettings v-else-if="activeTab === 'writing'" />
          <VectorStoreManagement v-else />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import LLMSettings from '@/components/LLMSettings.vue'
import WritingModelSettings from '@/components/WritingModelSettings.vue'
import VectorStoreManagement from '@/components/VectorStoreManagement.vue'

const activeTab = ref<'llm' | 'writing' | 'vector'>('llm')
</script>
