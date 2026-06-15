<template>
  <div class="relative min-h-screen overflow-hidden bg-cyber-darkest font-mono">

    <!-- 网格底纹 -->
    <div class="pointer-events-none fixed inset-0 z-0 bg-grid-pattern bg-grid opacity-40" />
    <!-- 扫描线 -->
    <div class="scan-line-overlay" />

    <main class="relative z-10 mx-auto max-w-lg px-4 pb-12 pt-8">
      <!-- 标题 -->
      <header class="mb-8 text-center">
        <h1 class="text-xl font-bold uppercase tracking-[0.2em] text-neon text-glow-neon">
          打印历史
        </h1>
        <p class="mt-1 text-[10px] tracking-[0.15em] text-volt/60">
          // PRINT HISTORY //
        </p>
      </header>

      <!-- 加载 -->
      <div v-if="loading" class="cyber-panel p-8 text-center">
        <span class="inline-block h-6 w-6 animate-spin rounded-full border-2 border-neon/30 border-t-neon" />
        <p class="mt-3 text-xs text-gray-500">加载中...</p>
      </div>

      <!-- 错误 -->
      <div v-else-if="error" class="cyber-panel border-red-400/30 bg-red-500/5 p-4 text-center">
        <p class="text-xs text-red-400">{{ error }}</p>
      </div>

      <!-- 空状态 -->
      <div v-else-if="jobs.length === 0" class="cyber-panel p-8 text-center">
        <p class="text-sm text-gray-500">暂无打印记录</p>
        <p class="mt-1 text-[10px] text-gray-600">上传文件后将在此处显示</p>
      </div>

      <!-- 任务列表 -->
      <div v-else class="flex flex-col gap-3">
        <div
          v-for="job in jobs"
          :key="job.id"
          class="cyber-panel cursor-pointer p-4 transition-all duration-200 hover:border-cyber-border/80"
          @click="router.push(`/status/${job.id}`)"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0 flex-1">
              <!-- 文件名 -->
              <p class="truncate text-xs text-gray-200">{{ job.file_name }}</p>

              <!-- 时间 -->
              <p class="mt-1 text-[10px] text-gray-600 font-mono">
                {{ formatTime(job.created_at) }}
              </p>

              <!-- 错误信息 -->
              <p v-if="job.error_msg" class="mt-1 truncate text-[10px] text-red-400/60">
                {{ job.error_msg }}
              </p>

              <!-- AI 摘要预览 -->
              <p v-if="job.summary_text" class="mt-1 truncate text-[10px] text-volt/50">
                {{ job.summary_text.slice(0, 80) }}{{ job.summary_text.length > 80 ? '...' : '' }}
              </p>
            </div>

            <!-- 状态标签 -->
            <span
              :class="[
                'shrink-0 rounded-full px-2.5 py-0.5 text-[10px] uppercase tracking-wider font-bold',
                statusClass(job.status),
              ]"
            >
              {{ statusLabel(job.status) }}
            </span>
          </div>
        </div>

        <!-- 加载更多 -->
        <div v-if="hasMore" class="text-center">
          <button
            class="cyber-panel px-6 py-2 text-[10px] uppercase tracking-wider text-gray-500 hover:text-neon/60 transition-colors"
            @click="loadMore"
          >
            [ 加载更多 ]
          </button>
        </div>
      </div>

      <!-- 返回 -->
      <div class="mt-8 text-center">
        <button
          class="text-[11px] uppercase tracking-wider text-cyan hover:text-cyan/80 transition-colors"
          @click="router.push('/')"
        >
          ← 返回上传页
        </button>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { listJobs } from '@/composables/useApi'

const route = useRoute()
const router = useRouter()

const nodeId = route.query.node || null

const jobs = ref([])
const loading = ref(true)
const error = ref('')
const hasMore = ref(false)
const MAX_PER_PAGE = 20

// 状态映射
function statusLabel(status) {
  const map = {
    pending: '等待',
    printing: '打印中',
    completed: '完成',
    failed: '失败',
  }
  return map[status] || status
}

function statusClass(status) {
  const map = {
    completed: 'bg-neon/10 text-neon border border-neon/20',
    printing: 'bg-yellow-400/10 text-yellow-400 border border-yellow-400/20',
    failed: 'bg-red-400/10 text-red-400 border border-red-400/20',
    pending: 'bg-gray-400/10 text-gray-400 border border-gray-400/20',
  }
  return map[status] || ''
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

async function load() {
  try {
    const data = await listJobs(nodeId, MAX_PER_PAGE, 0)
    jobs.value = data
    hasMore.value = data.length >= MAX_PER_PAGE
  } catch (e) {
    error.value = '加载失败，请检查网络连接'
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  try {
    const data = await listJobs(nodeId, MAX_PER_PAGE, jobs.value.length)
    if (data.length > 0) {
      jobs.value.push(...data)
    }
    hasMore.value = data.length >= MAX_PER_PAGE
  } catch {
    // silently fail on load more
  }
}

onMounted(load)
</script>
