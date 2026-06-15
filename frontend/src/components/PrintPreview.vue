<!-- ═══════════════════════════════════════════════════════════════════
     PrintPreview.vue — Y2K Cyber Dawn PDF 预览面板
     接收 File 对象 → FileReader 读取 → pdf.js 渲染
     ═══════════════════════════════════════════════════════════════════ -->
<template>
  <div v-if="file" class="animate-slide-up">
    <!-- ── 区块标题 ── -->
    <div class="mb-3 flex items-center justify-between">
      <h2 class="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-cyan">
        <span class="inline-block h-3 w-3 rounded-sm border border-cyan/40 bg-cyan/10" />
        03 / 打印预览
      </h2>
      <button
        class="flex items-center gap-1 text-[10px] uppercase tracking-wider text-gray-500 hover:text-neon/70 transition-colors"
        :class="{ 'text-neon/50': showPreview }"
        @click="showPreview = !showPreview"
      >
        <span>{{ showPreview ? '[ − 收起 ]' : '[ + 展开 ]' }}</span>
      </button>
    </div>

    <!-- ═══ 预览面板 ═══ -->
    <Transition name="preview-expand">
      <div v-if="showPreview" class="cyber-panel overflow-hidden">
        <!-- 顶部控制栏 -->
        <div class="flex items-center justify-between border-b border-cyber-border/50 px-5 py-3">
          <div class="flex items-center gap-3">
            <span class="text-[10px] text-gray-500 uppercase tracking-wider">
              {{ file.name }}
            </span>
            <span class="text-[9px] text-neon/40">
              {{ formatFileSize(file.size) }}
            </span>
          </div>
          <div v-if="totalPages > 0" class="flex items-center gap-1">
            <span class="text-[10px] font-mono text-neon/60 tabular-nums">
              {{ currentPage }} / {{ totalPages }}
            </span>
          </div>
        </div>

        <!-- ═══ PDF 渲染区 ═══ -->
        <div class="relative bg-cyber-darkest">
          <!-- 装饰: 四角标记 -->
          <span class="absolute left-2 top-2 z-10 text-[8px] text-neon/10">┌ ─ ─┐</span>
          <span class="absolute right-2 top-2 z-10 text-[8px] text-neon/10">┌ ─ ─┐</span>
          <span class="absolute bottom-2 left-2 z-10 text-[8px] text-neon/10">└ ─ ─┘</span>
          <span class="absolute bottom-2 right-2 z-10 text-[8px] text-neon/10">└ ─ ─┘</span>

          <!-- PDF 内容 -->
          <div class="flex min-h-[320px] items-center justify-center p-4">
            <!-- 加载动画 -->
            <div v-if="loading" class="flex flex-col items-center gap-3 py-12">
              <svg class="h-10 w-10 animate-spin text-neon/30" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="1.5" stroke-dasharray="32" stroke-dashoffset="8" />
              </svg>
              <p class="text-[10px] uppercase tracking-[0.3em] text-neon/40 animate-pulse">
                RENDERING...
              </p>
            </div>

            <!-- 错误 -->
            <div v-else-if="error" class="py-8 text-center">
              <span class="text-[10px] uppercase tracking-wider text-red-400/60">
                {{ error }}
              </span>
            </div>

            <!-- PDF 页面渲染 -->
            <VuePdfEmbed
              v-else-if="pdfSource"
              :key="currentPage"
              :source="pdfSource"
              :page="currentPage"
              class="max-w-full"
              :style="{ maxHeight: '60vh' }"
            />
          </div>

          <!-- 页码导航条 -->
          <div
            v-if="totalPages > 1 && !loading"
            class="flex items-center justify-center gap-3 border-t border-cyber-border/50 px-4 py-3"
          >
            <button
              class="flex h-8 w-8 items-center justify-center rounded-md border border-cyber-border text-neon/50 transition-all hover:border-neon/30 hover:text-neon hover:shadow-[0_0_10px_rgba(57,255,20,0.1)] disabled:opacity-20 disabled:hover:border-cyber-border disabled:hover:shadow-none"
              :disabled="currentPage <= 1"
              @click="currentPage = Math.max(1, currentPage - 1)"
            >
              <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
            </button>

            <!-- 页码点 -->
            <div class="flex items-center gap-1.5">
              <button
                v-for="page in totalPages"
                :key="page"
                :class="[
                  'h-2 rounded-full transition-all duration-300',
                  page === currentPage
                    ? 'w-6 bg-neon shadow-[0_0_6px_rgba(57,255,20,0.5)]'
                    : 'w-2 bg-cyber-border hover:bg-gray-500',
                ]"
                @click="currentPage = page"
              />
            </div>

            <button
              class="flex h-8 w-8 items-center justify-center rounded-md border border-cyber-border text-neon/50 transition-all hover:border-neon/30 hover:text-neon hover:shadow-[0_0_10px_rgba(57,255,20,0.1)] disabled:opacity-20 disabled:hover:border-cyber-border disabled:hover:shadow-none"
              :disabled="currentPage >= totalPages"
              @click="currentPage = Math.min(totalPages, currentPage + 1)"
            >
              <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>
        </div>

        <!-- 底部信息栏 -->
        <div class="border-t border-cyber-border/50 px-5 py-2.5">
          <div class="flex items-center justify-between text-[9px] text-gray-600">
            <span class="flex items-center gap-1.5">
              <span class="inline-block h-1.5 w-1.5 rounded-full" :class="totalPages > 0 ? 'bg-neon/30' : 'bg-gray-700'" />
              {{ totalPages > 0 ? `${totalPages} 页` : '读取中...' }}
            </span>
            <span v-if="currentPage === 1 && totalPages > 0" class="text-neon/20">
              预览第 1 页
            </span>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<!-- ═══════════════════════════════════════════════════════════════════
     SCRIPT
     ═══════════════════════════════════════════════════════════════════ -->
<script setup>
import { ref, watch, shallowRef, onMounted } from 'vue'
import VuePdfEmbed from 'vue-pdf-embed'

const props = defineProps({
  file: {
    type: File,
    default: null,
  },
})

// ── 状态 ──
const showPreview = ref(true)
const currentPage = ref(1)
const totalPages = ref(0)
const loading = ref(false)
const error = ref('')
const pdfSource = shallowRef(null)

// ── Worker 路径 — dev 直接引用 node_modules, prod 用 static copy ──
onMounted(async () => {
  const pdfjs = await import('pdfjs-dist')
  // pdfjs-dist v3+/v4+ 顶层导出 GlobalWorkerOptions
  if (!pdfjs.GlobalWorkerOptions.workerSrc) {
    pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.js'
  }
})

// ── 监听文件变化 → 读取并解析 PDF ──
watch(
  () => props.file,
  async (file) => {
    if (!file) {
      if (pdfSource.value) {
        URL.revokeObjectURL(pdfSource.value)
      }
      pdfSource.value = null
      totalPages.value = 0
      currentPage.value = 1
      error.value = ''
      loading.value = false
      return
    }

    loading.value = true
    error.value = ''
    currentPage.value = 1

    try {
      // 使用 Blob URL 作为 vue-pdf-embed 的数据源 (避免 Uint8Array 缓冲区问题)
      if (pdfSource.value) {
        URL.revokeObjectURL(pdfSource.value)
      }
      pdfSource.value = URL.createObjectURL(file)

      // 获取总页数
      const pdfjs = await import('pdfjs-dist')
      const buffer = await file.arrayBuffer()
      const loadingTask = pdfjs.getDocument({ data: buffer })
      const doc = await loadingTask.promise
      totalPages.value = doc.numPages

      loading.value = false
    } catch (e) {
      loading.value = false
      error.value = 'PDF 渲染失败，文件可能已损坏'
      console.error('PDF preview error:', e)
    }
  },
  { immediate: true }
)

// ── 工具 ──
function formatFileSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return `${size.toFixed(i > 0 ? 1 : 0)} ${units[i]}`
}
</script>

<style scoped>
/* ── 预览面板展开/收起动画 ── */
.preview-expand-enter-active,
.preview-expand-leave-active {
  transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}
.preview-expand-enter-from,
.preview-expand-leave-to {
  opacity: 0;
  max-height: 0;
  transform: translateY(-8px);
}
.preview-expand-enter-to,
.preview-expand-leave-from {
  opacity: 1;
  max-height: 800px;
}
</style>
