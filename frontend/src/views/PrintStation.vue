<template>
  <!-- ═══════════════════════════════════════════════════════════════════
       PrintStation.vue — Y2K Cyber Dawn 赛博打印控制台
       移动端扫码入口 → 文件上传 → 参数配置 → 提交云端
       ═══════════════════════════════════════════════════════════════════ -->
  <div class="relative min-h-screen overflow-hidden bg-cyber-darkest font-mono">

    <!-- ═══ 背景装饰 ═══ -->

    <!-- 网格底纹 -->
    <div class="pointer-events-none fixed inset-0 z-0 bg-grid-pattern bg-grid opacity-40" />

    <!-- 扫描线动画 -->
    <div class="scan-line-overlay" />

    <!-- 顶部霓虹光晕 -->
    <div class="pointer-events-none fixed -top-40 left-1/2 z-0 h-80 w-[600px] -translate-x-1/2 rounded-full bg-neon/5 blur-[120px]" />
    <div class="pointer-events-none fixed top-0 right-0 z-0 h-64 w-64 rounded-full bg-volt/5 blur-[100px]" />

    <!-- ═══ 主容器 ═══ -->

    <main class="relative z-10 mx-auto max-w-lg px-4 pb-20 pt-8">
      <!-- ═══════════════════════════════════════════════
           标题区
           ═══════════════════════════════════════════════ -->
      <header class="mb-8 text-center">
        <!-- 状态指示灯行 -->
        <div class="mb-4 flex items-center justify-center gap-3">
          <span class="flex items-center gap-1.5 text-[10px] uppercase tracking-[0.3em] text-neon/60">
            <span class="inline-block h-2 w-2 rounded-full bg-neon shadow-neon animate-glow-pulse shadow-neon/50" />
            NODE ONLINE
          </span>
          <span class="text-cyber-border">|</span>
          <span class="text-[10px] uppercase tracking-[0.3em] text-gray-500">
            {{ currentTime }}
          </span>
        </div>

        <!-- 主标题 -->
        <h1 class="group relative inline-block">
          <span class="relative z-10 text-3xl font-bold uppercase tracking-[0.2em] text-neon text-glow-neon">
            星火智造
          </span>
          <span class="absolute inset-0 z-0 animate-flicker text-3xl font-bold uppercase tracking-[0.2em] text-neon/30 blur-sm">
            星火智造
          </span>
        </h1>

        <p class="mt-2 font-sans text-sm tracking-[0.15em] text-volt text-glow-volt">
          // STARFIRE PRINT HUB //
        </p>

        <div class="mt-3 flex items-center justify-center gap-2">
          <span class="inline-block h-px w-8 bg-gradient-to-r from-transparent to-neon/40" />
          <span class="text-[10px] uppercase tracking-[0.2em] text-gray-500">Cyber Dawn v1.0</span>
          <span class="inline-block h-px w-8 bg-gradient-to-l from-transparent to-neon/40" />
        </div>
      </header>

      <!-- ═══════════════════════════════════════════════
           文件上传区
           ═══════════════════════════════════════════════ -->
      <section class="animate-slide-up mb-6">
        <h2 class="mb-3 flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-cyan">
          <span class="inline-block h-3 w-3 rounded-sm border border-cyan/40 bg-cyan/10" />
          01 / 选择文件
        </h2>

        <!-- 上传卡片 -->
        <div
          ref="dropZoneRef"
          :class="[
            'cyber-panel relative cursor-pointer overflow-hidden p-6 transition-all duration-300',
            isDragging
              ? 'border-neon shadow-neon/20'
              : 'hover:border-cyber-border/80',
          ]"
          @click="triggerFileInput"
          @dragover.prevent="isDragging = true"
          @dragleave.prevent="isDragging = false"
          @drop.prevent="handleDrop"
        >
          <!-- 装饰: 四角括号 -->
          <span class="absolute left-2 top-2 text-[8px] text-neon/20">┌ ─ ─┐</span>
          <span class="absolute right-2 top-2 text-[8px] text-neon/20">┌ ─ ─┐</span>
          <span class="absolute bottom-2 left-2 text-[8px] text-neon/20">└ ─ ─┘</span>
          <span class="absolute bottom-2 right-2 text-[8px] text-neon/20">└ ─ ─┘</span>

          <!-- 空状态: 未选文件 -->
          <div v-if="!selectedFile" class="flex flex-col items-center gap-3 py-6">
            <div class="relative">
              <svg class="h-16 w-16 text-neon/20" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="0.8">
                <path stroke-linecap="round" stroke-linejoin="round"
                  d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
              </svg>
              <div class="absolute -bottom-1 left-1/2 h-6 w-px -translate-x-1/2 animate-pulse bg-neon/30" />
            </div>
            <p class="text-sm text-gray-400">
              <span class="text-neon/70">[ 点击选择 ]</span>
              或拖拽文件至此
            </p>
            <p class="text-[10px] text-gray-600">
              支持 PDF / DOCX / TXT / PNG (最大 20MB)
            </p>
          </div>

          <!-- 已选文件 -->
          <div v-else class="flex flex-col items-center gap-2 py-4">
            <div class="flex items-center gap-3">
              <svg class="h-8 w-8 text-neon/60" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
                <path stroke-linecap="round" stroke-linejoin="round"
                  d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25" />
              </svg>
              <div class="text-left">
                <p class="max-w-[200px] truncate text-sm text-neon">{{ selectedFile.name }}</p>
                <p class="text-[11px] text-gray-500">{{ formatFileSize(selectedFile.size) }}</p>
              </div>
            </div>
            <button
              type="button"
              class="mt-2 text-[11px] uppercase tracking-wider text-red-400/70 hover:text-red-400 transition-colors"
              @click.stop="clearFile"
            >
              [ X ] 移除
            </button>
          </div>

          <!-- 隐藏的 input -->
          <input
            ref="fileInputRef"
            type="file"
            :accept="ALLOWED_FILE_TYPES"
            class="hidden"
            @change="handleFileSelect"
          />
        </div>
      </section>

      <!-- ═══════════════════════════════════════════════
           打印预览 (选中文件后自动展示)
           ═══════════════════════════════════════════════ -->
      <PrintPreview :file="selectedFile" class="mb-6" />

      <!-- ═══════════════════════════════════════════════
           打印参数面板
           ═══════════════════════════════════════════════ -->
      <section class="animate-slide-up mb-6" style="animation-delay: 0.1s">
        <h2 class="mb-3 flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-cyan">
          <span class="inline-block h-3 w-3 rounded-sm border border-cyan/40 bg-cyan/10" />
          02 / 打印参数
        </h2>

        <div class="cyber-panel divide-y divide-cyber-border/50 overflow-hidden">
          <!-- ── 纸张大小 ── -->
          <div class="flex items-center justify-between px-5 py-4">
            <span class="text-xs uppercase tracking-wider text-gray-400">纸张大小</span>
            <div class="flex gap-1 rounded-md bg-cyber-mid p-0.5">
              <button
                v-for="size in paperSizes"
                :key="size.value"
                :class="[
                  'px-4 py-1.5 text-xs rounded-sm transition-all duration-200',
                  printOptions.media === size.value
                    ? 'bg-neon/15 text-neon shadow-[0_0_10px_rgba(57,255,20,0.15)]'
                    : 'text-gray-500 hover:text-gray-300',
                ]"
                @click="printOptions.media = size.value"
              >
                {{ size.label }}
              </button>
            </div>
          </div>

          <!-- ── 页面拼版 (N-up) ── -->
          <div class="flex items-center justify-between px-5 py-4">
            <span class="text-xs uppercase tracking-wider text-gray-400">页面拼版</span>
            <div class="flex gap-1 rounded-md bg-cyber-mid p-0.5">
              <button
                v-for="nup in nUpOptions"
                :key="nup.value"
                :class="[
                  'px-3 py-1.5 text-xs rounded-sm transition-all duration-200',
                  printOptions.number_up === nup.value
                    ? 'bg-volt/15 text-volt shadow-[0_0_10px_rgba(180,77,255,0.15)]'
                    : 'text-gray-500 hover:text-gray-300',
                ]"
                @click="printOptions.number_up = nup.value"
              >
                {{ nup.label }}
              </button>
            </div>
          </div>

          <!-- ── 单双面打印 (Toggle) ── -->
          <div class="flex items-center justify-between px-5 py-4">
            <div>
              <span class="text-xs uppercase tracking-wider text-gray-400">双面打印</span>
              <p class="mt-0.5 text-[10px] text-gray-600">
                {{ isDuplex ? '长边翻转' : '单面' }}
              </p>
            </div>
            <button
              type="button"
              role="switch"
              :aria-checked="isDuplex"
              :class="[
                'relative inline-flex h-7 w-12 shrink-0 cursor-pointer items-center rounded-full transition-all duration-300',
                isDuplex
                  ? 'bg-neon/20 shadow-[0_0_15px_rgba(57,255,20,0.2)]'
                  : 'bg-cyber-mid border border-cyber-border',
              ]"
              @click="toggleDuplex"
            >
              <span
                :class="[
                  'inline-flex h-5 w-5 items-center justify-center rounded-full transition-all duration-300',
                  isDuplex
                    ? 'translate-x-6 bg-neon shadow-[0_0_8px_rgba(57,255,20,0.5)]'
                    : 'translate-x-1 bg-gray-600',
                ]"
              >
                <span
                  v-if="isDuplex"
                  class="text-[8px] text-cyber-darkest font-bold"
                >⇄</span>
              </span>
            </button>
          </div>

          <!-- ── AI 智能摘要 (Toggle) ── -->
          <div class="flex items-center justify-between px-5 py-4">
            <div>
              <span class="text-xs uppercase tracking-wider text-gray-400">AI 智能摘要</span>
              <p class="mt-0.5 text-[10px] text-gray-600">
                {{ aiSummary ? '在 PDF 前添加摘要页' : '关闭' }}
              </p>
            </div>
            <button
              type="button"
              role="switch"
              :aria-checked="aiSummary"
              :class="[
                'relative inline-flex h-7 w-12 shrink-0 cursor-pointer items-center rounded-full transition-all duration-300',
                aiSummary
                  ? 'bg-volt/20 shadow-[0_0_15px_rgba(180,77,255,0.2)]'
                  : 'bg-cyber-mid border border-cyber-border',
              ]"
              @click="aiSummary = !aiSummary"
            >
              <span
                :class="[
                  'inline-flex h-5 w-5 items-center justify-center rounded-full transition-all duration-300',
                  aiSummary
                    ? 'translate-x-6 bg-volt shadow-[0_0_8px_rgba(180,77,255,0.5)]'
                    : 'translate-x-1 bg-gray-600',
                ]"
              >
                <span
                  v-if="aiSummary"
                  class="text-[8px] text-white font-bold"
                >AI</span>
              </span>
            </button>
          </div>

          <!-- ── 份数 ── -->
          <div class="flex items-center justify-between px-5 py-4">
            <span class="text-xs uppercase tracking-wider text-gray-400">打印份数</span>
            <div class="flex items-center gap-1 rounded-md bg-cyber-mid">
              <button
                class="px-3 py-1.5 text-xs text-gray-400 hover:text-neon transition-colors"
                :disabled="printOptions.copies <= 1"
                @click="printOptions.copies = Math.max(1, printOptions.copies - 1)"
              >
                −
              </button>
              <span class="w-8 text-center text-sm text-neon font-bold tabular-nums">
                {{ printOptions.copies }}
              </span>
              <button
                class="px-3 py-1.5 text-xs text-gray-400 hover:text-neon transition-colors"
                :disabled="printOptions.copies >= 99"
                @click="printOptions.copies = Math.min(99, printOptions.copies + 1)"
              >
                +
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- ═══════════════════════════════════════════════
           提交按钮区
           ═══════════════════════════════════════════════ -->
      <section class="animate-slide-up" style="animation-delay: 0.2s">
        <button
          :disabled="!selectedFile || isSubmitting"
          class="btn-cyber group w-full"
          :class="[
            !selectedFile || isSubmitting
              ? 'bg-cyber-mid text-gray-600 border border-cyber-border cursor-not-allowed'
              : 'bg-neon/10 text-neon border border-neon/30 hover:bg-neon/20 hover:border-neon/60 active:scale-[0.98]',
          ]"
          @click="handleSubmit"
        >
          <!-- 默认文案 -->
          <span v-if="!isSubmitting" class="flex items-center justify-center gap-2">
            <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round"
                d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12a59.77 59.77 0 01-3.27 8.874L6 12z" />
            </svg>
            发送至云端队列
          </span>

          <!-- 提交中文案 -->
          <span v-else class="flex items-center justify-center gap-2">
            <span class="inline-block h-4 w-4 animate-spin rounded-full border-2 border-neon/30 border-t-neon" />
            正在发送至云端队列...
          </span>

          <!-- 悬停发光条 -->
          <span
            v-if="selectedFile && !isSubmitting"
            class="absolute inset-x-0 -bottom-px h-px bg-gradient-to-r from-transparent via-neon to-transparent opacity-0 transition-opacity group-hover:opacity-100"
          />
        </button>

        <!-- 提交进度动画 -->
        <Transition name="progress">
          <div v-if="isSubmitting" class="mt-4 cyber-panel overflow-hidden p-4">
            <!-- 进度条容器 -->
            <div class="relative mb-3 h-1 overflow-hidden rounded-full bg-cyber-mid">
              <div
                class="h-full animate-[dataStream_1.5s_ease-in-out_infinite] rounded-full"
                style="
                  background: linear-gradient(90deg, transparent, #39ff14, #b44dff, #39ff14, transparent);
                  background-size: 200% 100%;
                  width: 80%;
                "
              />
            </div>

            <!-- 状态文字流 -->
            <div class="flex flex-col gap-1 font-mono text-[10px]">
              <p class="flex items-center gap-2 text-neon/80">
                <span class="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-neon" />
                <span class="animate-pulse">{{ submittingMessages[currentMessageIndex] }}</span>
              </p>
              <p class="text-gray-600">
                > encrypting payload...
                <span class="text-neon/40">{{ Math.floor(submitProgress) }}%</span>
              </p>
              <p class="text-gray-600">
                > connecting to starfire://cloud-node
              </p>
              <p class="flex items-center gap-1 text-gray-600">
                <span class="inline-block h-1 w-1 rounded-full bg-cyan/50" />
                {{ submitProgress >= 30 ? 'handshake established' : 'establishing handshake...' }}
              </p>
              <p v-if="submitProgress >= 60" class="flex items-center gap-1 text-gray-600">
                <span class="inline-block h-1 w-1 rounded-full bg-volt/50" />
                transferring to printer queue...
              </p>
            </div>

            <!-- AI 摘要特殊提示 -->
            <div v-if="aiSummary" class="mt-3 flex items-center gap-2 rounded-md bg-volt/5 px-3 py-2 border border-volt/10">
              <span class="text-[16px]">🧠</span>
              <p class="text-[10px] text-volt/70">
                AI 摘要将在云端异步生成，不影响打印速度
              </p>
            </div>
          </div>
        </Transition>
      </section>

      <!-- ═══════════════════════════════════════════════
           成功提示
           ═══════════════════════════════════════════════ -->
      <Transition name="slide">
        <div v-if="showSuccess" class="mt-6 cyber-panel border-neon/30 bg-neon/5 p-5 text-center">
          <div class="mb-2 text-2xl">✓</div>
          <p class="text-sm text-neon text-glow-neon">任务已成功发送</p>
          <p class="mt-1 text-[10px] text-gray-500">JOB ID: {{ submittedJobId }}</p>
          <button
            class="mt-4 text-[11px] uppercase tracking-wider text-cyan hover:text-cyan/80 transition-colors"
            @click="resetForm"
          >
            [ 发送新任务 ]
          </button>
        </div>
      </Transition>

      <!-- ═══════════════════════════════════════════════
           错误提示
           ═══════════════════════════════════════════════ -->
      <Transition name="slide">
        <div v-if="errorMessage" class="mt-4 mb-4 cyber-panel border-red-400/30 bg-red-500/5 p-4">
          <p class="flex items-start gap-2 text-xs text-red-400">
            <span class="mt-0.5 shrink-0 text-red-400 font-bold">!</span>
            <span class="flex-1">{{ errorMessage }}</span>
            <button class="shrink-0 text-red-400/50 hover:text-red-400 transition-colors" @click="errorMessage = ''">
              [X]
            </button>
          </p>
        </div>
      </Transition>

      <!-- ═══════════════════════════════════════════════
           底部装饰
           ═══════════════════════════════════════════════ -->
      <footer class="mt-12 text-center">
        <div class="flex items-center justify-center gap-3">
          <span class="h-px w-6 bg-cyber-border" />
          <span class="text-[9px] uppercase tracking-[0.3em] text-gray-700">Starfire</span>
          <span class="inline-block h-1.5 w-1.5 rounded-full bg-neon/30" />
          <span class="text-[9px] uppercase tracking-[0.3em] text-gray-700">Print Hub</span>
          <span class="h-px w-6 bg-cyber-border" />
        </div>
      </footer>
    </main>
  </div>
</template>

<!-- ═══════════════════════════════════════════════════════════════════
     SCRIPT
     ═══════════════════════════════════════════════════════════════════ -->
<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { uploadPrintJob } from '@/composables/useApi'
import PrintPreview from '@/components/PrintPreview.vue'
import { ALLOWED_FILE_TYPES, ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB } from '@/utils/constants'

// ── 路由 ──
import { useRouter } from 'vue-router'
const router = useRouter()

// ═══════════════════════════════════════════════════════════════
// 响应式状态
// ═══════════════════════════════════════════════════════════════

// 文件
const fileInputRef = ref(null)
const dropZoneRef = ref(null)
const selectedFile = ref(null)
const isDragging = ref(false)

// 打印参数
const printOptions = reactive({
  media: 'A4',        // 纸张大小
  number_up: 1,        // 拼版 (1/2/4)
  sides: 'one-sided',  // 单双面
  copies: 1,           // 份数
})

// AI 摘要
const aiSummary = ref(false)

// 提交状态
const isSubmitting = ref(false)
const submitProgress = ref(0)
const showSuccess = ref(false)
const submittedJobId = ref('')
const errorMessage = ref('')

// 进度动画文案轮播
const submittingMessages = [
  'UPLOADING...',
  'ENCRYPTING...',
  'QUEUING...',
  'PROCESSING...',
  'INITIATING DATA STREAM...',
]
const currentMessageIndex = ref(0)
let messageTimer = null
let progressTimer = null

// 当前时间
const currentTime = ref('')
let clockTimer = null

// ═══════════════════════════════════════════════════════════════
// 计算属性
// ═══════════════════════════════════════════════════════════════

const isDuplex = computed({
  get: () => printOptions.sides === 'two-sided-long-edge',
  set: (val) => {
    printOptions.sides = val ? 'two-sided-long-edge' : 'one-sided'
  },
})

// ═══════════════════════════════════════════════════════════════
// 选项常量
// ═══════════════════════════════════════════════════════════════

const paperSizes = [
  { label: 'A4', value: 'A4' },
  { label: 'A3', value: 'A3' },
  { label: 'LTR', value: 'Letter' },
]

const nUpOptions = [
  { label: '1合1', value: 1 },
  { label: '2合1', value: 2 },
  { label: '4合1', value: 4 },
]

// ═══════════════════════════════════════════════════════════════
// 方法
// ═══════════════════════════════════════════════════════════════

function triggerFileInput() {
  if (!isSubmitting.value) {
    fileInputRef.value?.click()
  }
}

function handleFileSelect(event) {
  const file = event.target.files?.[0]
  if (file) validateAndSetFile(file)
  // 重置 input 以允许重复选择同一文件
  event.target.value = ''
}

function handleDrop(event) {
  isDragging.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) validateAndSetFile(file)
}

function validateAndSetFile(file) {
  errorMessage.value = ''

  // 检查扩展名
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (!ext || !ALLOWED_EXTENSIONS.includes(ext)) {
    errorMessage.value = `不支持的文件类型: .${ext}`
    return
  }

  // 检查大小
  if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
    errorMessage.value = `文件过大 (最大 ${MAX_FILE_SIZE_MB}MB)`
    return
  }

  selectedFile.value = file
}

function clearFile() {
  selectedFile.value = null
  fileInputRef.value.value = ''
}

function toggleDuplex() {
  isDuplex.value = !isDuplex.value
}

function formatFileSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return `${size.toFixed(i > 0 ? 1 : 0)} ${units[i]}`
}

// ═══════════════════════════════════════════════════════════════
// 提交逻辑
// ═══════════════════════════════════════════════════════════════

async function handleSubmit() {
  if (!selectedFile.value || isSubmitting.value) return

  isSubmitting.value = true
  showSuccess.value = false
  errorMessage.value = ''
  submitProgress.value = 0

  // 启动进度动画
  startSubmitAnimation()

  try {
    // 构建 CUPS 参数
    const cupsOptions = {
      media: printOptions.media,
      number_up: printOptions.number_up,
      sides: printOptions.sides,
      copies: printOptions.copies,
    }

    // 调用云端 API
    const response = await uploadPrintJob(
      selectedFile.value,
      cupsOptions,
      aiSummary.value,
    )

    // 成功
    submitProgress.value = 100
    submittedJobId.value = response.job_id

    // 短暂延迟展示完成效果
    await sleep(600)

    stopSubmitAnimation()
    isSubmitting.value = false
    showSuccess.value = true

  } catch (err) {
    stopSubmitAnimation()
    isSubmitting.value = false

    if (err.response) {
      const detail = err.response.data?.detail
      errorMessage.value = `服务器错误 (${err.response.status}): ${detail || '请稍后重试'}`
    } else if (err.code === 'ECONNABORTED') {
      errorMessage.value = '请求超时，请检查网络连接'
    } else if (err.message?.includes('Network Error')) {
      errorMessage.value = '网络连接失败，请确认已连接到局域网'
    } else {
      errorMessage.value = err.message || '未知错误，请重试'
    }
  }
}

function startSubmitAnimation() {
  // 进度条模拟
  progressTimer = setInterval(() => {
    if (submitProgress.value < 90) {
      // 模拟非匀速增长: 先快后慢
      const increment = Math.max(1, (90 - submitProgress.value) / 8)
      submitProgress.value += increment
    }
  }, 300)

  // 文案轮播
  messageTimer = setInterval(() => {
    currentMessageIndex.value = (currentMessageIndex.value + 1) % submittingMessages.length
  }, 2000)
}

function stopSubmitAnimation() {
  if (progressTimer) { clearInterval(progressTimer); progressTimer = null }
  if (messageTimer) { clearInterval(messageTimer); messageTimer = null }
}

function resetForm() {
  selectedFile.value = null
  showSuccess.value = false
  submittedJobId.value = ''
  submitProgress.value = 0
  printOptions.media = 'A4'
  printOptions.number_up = 1
  printOptions.sides = 'one-sided'
  printOptions.copies = 1
  aiSummary.value = false
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

// ═══════════════════════════════════════════════════════════════
// 时钟
// ═══════════════════════════════════════════════════════════════

function updateClock() {
  const now = new Date()
  currentTime.value = now.toLocaleTimeString('zh-CN', { hour12: false })
}

onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
})

onUnmounted(() => {
  if (clockTimer) clearInterval(clockTimer)
  stopSubmitAnimation()
})
</script>

<!-- ═══════════════════════════════════════════════════════════════════
     STYLE (作用域)
     ═══════════════════════════════════════════════════════════════════ -->
<style scoped>
/* ── 过渡动画 ── */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.35s cubic-bezier(0.16, 1, 0.3, 1);
}
.slide-enter-from {
  opacity: 0;
  transform: translateY(16px) scale(0.97);
}
.slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

.progress-enter-active,
.progress-leave-active {
  transition: all 0.3s ease-out;
}
.progress-enter-from {
  opacity: 0;
  max-height: 0;
  transform: translateY(-10px);
}
.progress-enter-to {
  opacity: 1;
  max-height: 300px;
}
.progress-leave-from {
  opacity: 1;
  max-height: 300px;
}
.progress-leave-to {
  opacity: 0;
  max-height: 0;
}

/* ── 自定义动画关键帧 ── */
@keyframes dataStream {
  0% { background-position: 200% 0%; }
  100% { background-position: -200% 0%; }
}
</style>
