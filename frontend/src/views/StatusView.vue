<template>
  <div class="relative min-h-screen bg-cyber-darkest">
    <!-- 网格底纹 -->
    <div class="pointer-events-none fixed inset-0 z-0 bg-grid-pattern bg-grid opacity-40" />

    <main class="relative z-10 mx-auto max-w-lg px-4 py-12">
      <div class="cyber-panel p-8 text-center">
        <h2 class="text-lg text-neon text-glow-neon uppercase tracking-[0.2em]">任务状态</h2>

        <div v-if="loading" class="mt-6">
          <span class="inline-block h-6 w-6 animate-spin rounded-full border-2 border-neon/30 border-t-neon" />
          <p class="mt-3 text-xs text-gray-500">查询中...</p>
        </div>

        <div v-else-if="task" class="mt-6">
          <div class="mb-4 text-[10px] text-gray-500">JOB {{ task.id }}</div>

          <div
            :class="[
              'inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-xs uppercase tracking-wider font-bold',
              statusStyle,
            ]"
          >
            <span
              :class="[
                'inline-block h-2 w-2 rounded-full',
                task.status === 'completed' ? 'bg-neon animate-pulse' : 'bg-yellow-400 animate-pulse',
              ]"
            />
            {{ statusLabel }}
          </div>

          <div class="mt-6 grid gap-2 text-left text-xs">
            <div class="flex justify-between text-gray-500">
              <span>文件</span>
              <span class="text-gray-300">{{ task.file_name }}</span>
            </div>
            <div class="flex justify-between text-gray-500">
              <span>创建时间</span>
              <span class="text-gray-300 font-mono">{{ task.created_at }}</span>
            </div>
            <div v-if="task.summary_text" class="mt-3 rounded-md bg-cyber-surface p-3">
              <span class="text-volt text-xs">AI 摘要</span>
              <p class="mt-1 text-[11px] text-gray-400 whitespace-pre-wrap">{{ task.summary_text }}</p>
            </div>
          </div>
        </div>

        <div v-else class="mt-6">
          <p class="text-sm text-gray-500">任务不存在</p>
        </div>

        <button
          class="mt-8 text-[11px] uppercase tracking-wider text-cyan hover:text-cyan/80 transition-colors"
          @click="$router.push('/')"
        >
          ← 返回
        </button>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getJobStatus } from '@/composables/useApi'

const route = useRoute()
const jobId = route.params.jobId

const loading = ref(true)
const task = ref(null)

const statusLabel = computed(() => {
  const map = {
    pending: '等待打印',
    printing: '正在打印',
    completed: '已完成',
    failed: '失败',
  }
  return map[task.value?.status] || '未知'
})

const statusStyle = computed(() => {
  const map = {
    completed: 'bg-neon/10 text-neon border border-neon/30',
    printing: 'bg-yellow-400/10 text-yellow-400 border border-yellow-400/30',
    failed: 'bg-red-400/10 text-red-400 border border-red-400/30',
    pending: 'bg-gray-400/10 text-gray-400 border border-gray-400/30',
  }
  return map[task.value?.status] || ''
})

onMounted(async () => {
  try {
    task.value = await getJobStatus(jobId)
  } catch (e) {
    task.value = null
  } finally {
    loading.value = false
  }
})
</script>
