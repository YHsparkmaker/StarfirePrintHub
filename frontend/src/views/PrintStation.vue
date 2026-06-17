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
           使用信息 (科目 · 班级 · 校级标识)
           ═══════════════════════════════════════════════ -->
      <div class="mb-6 animate-slide-up grid grid-cols-3 gap-2">
        <div class="cyber-panel px-3 py-2">
          <label class="block text-[9px] uppercase tracking-[0.2em] text-gray-500 mb-1">科目</label>
          <input
            v-model="headerInfo.subject"
            class="w-full bg-transparent text-xs text-gray-200 placeholder:text-gray-700 outline-none"
            placeholder="如: 数学"
          />
        </div>
        <div class="cyber-panel px-3 py-2">
          <label class="block text-[9px] uppercase tracking-[0.2em] text-gray-500 mb-1">班级</label>
          <input
            v-model="headerInfo.className"
            class="w-full bg-transparent text-xs text-gray-200 placeholder:text-gray-700 outline-none"
            placeholder="如: 高二(3)班"
          />
        </div>
        <div class="cyber-panel px-3 py-2">
          <label class="block text-[9px] uppercase tracking-[0.2em] text-gray-500 mb-1">校标</label>
          <input
            v-model="headerInfo.schoolLabel"
            class="w-full bg-transparent text-xs text-gray-200 placeholder:text-gray-700 outline-none"
            placeholder="如: XX中学"
          />
        </div>
      </div>

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
          <template v-if="nodeId">
            <span class="text-cyber-border">|</span>
            <span class="text-[10px] uppercase tracking-[0.2em] text-cyan/60">
              {{ nodeId }}
            </span>
          </template>
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
           输入模式切换
           ═══════════════════════════════════════════════ -->
      <nav class="mb-6 flex rounded-lg bg-cyber-mid p-1">
        <button
          :class="[
            'flex-1 rounded-md py-2 text-xs uppercase tracking-wider transition-all duration-200',
            inputMode === 'file'
              ? 'bg-neon/10 text-neon shadow-[0_0_10px_rgba(57,255,20,0.1)]'
              : 'text-gray-500 hover:text-gray-300',
          ]"
          @click="inputMode = 'file'"
        >
          文件上传
        </button>
        <button
          :class="[
            'flex-1 rounded-md py-2 text-xs uppercase tracking-wider transition-all duration-200',
            inputMode === 'text'
              ? 'bg-volt/10 text-volt shadow-[0_0_10px_rgba(180,77,255,0.1)]'
              : 'text-gray-500 hover:text-gray-300',
          ]"
          @click="inputMode = 'text'"
        >
          文本编辑
        </button>
      </nav>

      <!-- ═══════════════════════════════════════════════
           文件上传区 (inputMode === 'file')
           ═══════════════════════════════════════════════ -->
      <section v-if="inputMode === 'file'" class="animate-slide-up mb-6">
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
            <button
              v-if="isExtractable(selectedFile)"
              type="button"
              :disabled="isExtractingText"
              class="mt-1 text-[11px] uppercase tracking-wider text-cyan/70 hover:text-cyan transition-colors"
              @click.stop="handleExtractAndEdit"
            >
              {{ isExtractingText ? '[ ... ] 提取中' : '[ + ] 提取并在线编辑' }}
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
           文本编辑区 (inputMode === 'text')
           ═══════════════════════════════════════════════ -->
      <section v-if="inputMode === 'text'" class="animate-slide-up mb-6">
        <h2 class="mb-3 flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-volt">
          <span class="inline-block h-3 w-3 rounded-sm border border-volt/40 bg-volt/10" />
          01 / Markdown 文本
        </h2>

        <!-- 工具栏 -->
        <div class="mb-2 flex flex-wrap gap-1">
          <button
            v-for="btn in toolbarButtons"
            :key="btn.label"
            class="rounded border border-cyber-border px-2.5 py-1 text-[11px] text-gray-400 transition-all hover:border-volt/30 hover:text-volt/70"
            :title="btn.title"
            @click="insertMarkdown(btn.insert)"
          >
            {{ btn.label }}
          </button>
        </div>

        <!-- 编辑区 -->
        <div class="cyber-panel overflow-hidden">
          <textarea
            v-model="textContent"
            class="w-full resize-y bg-transparent p-4 font-mono text-sm leading-relaxed text-gray-200 outline-none placeholder:text-gray-600"
            :style="{ minHeight: '220px' }"
            placeholder="# 在此输入 Markdown 文本...

支持 **粗体** *斜体* `代码` 列表 表格

行内公式: $E=mc^2$
块级公式:
$$
\\int_0^\\infty e^{-x^2} dx = \\frac{\\sqrt{\\pi}}{2}
$$
"
            spellcheck="false"
          />
        </div>

        <!-- 预览 -->
        <MarkdownPreview :text="textContent" class="mt-3" />
      </section>

      <!-- ═══════════════════════════════════════════════
           打印预览 (选中文件后自动展示)
           ═══════════════════════════════════════════════ -->
      <PrintPreview v-if="inputMode === 'file'" :file="selectedFile" class="mb-6" />

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

          <!-- ── 纸盒来源 ── -->
          <div class="flex items-center justify-between px-5 py-4">
            <div>
              <span class="text-xs uppercase tracking-wider text-gray-400">纸盒来源</span>
              <p class="mt-0.5 text-[10px] text-gray-600">
                {{ trayOptions.find(t => t.value === printOptions.media_source)?.label || '自动' }}
              </p>
            </div>
            <div class="flex gap-1 rounded-md bg-cyber-mid p-0.5">
              <button
                v-for="tray in trayOptions"
                :key="tray.value"
                :class="[
                  'px-2.5 py-1 text-[10px] rounded-sm transition-all duration-200',
                  printOptions.media_source === tray.value
                    ? 'bg-cyan/15 text-cyan shadow-[0_0_8px_rgba(0,175,175,0.1)]'
                    : 'text-gray-500 hover:text-gray-300',
                ]"
                @click="printOptions.media_source = tray.value"
              >
                {{ tray.label }}
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

          <!-- ── 打印方向 (横/竖) ── -->
          <div class="flex items-center justify-between px-5 py-4">
            <div>
              <span class="text-xs uppercase tracking-wider text-gray-400">打印方向</span>
              <p class="mt-0.5 text-[10px] text-gray-600">
                {{ isLandscape ? '横向 (Landscape)' : '竖向 (Portrait)' }}
              </p>
            </div>
            <div class="flex gap-1 rounded-md bg-cyber-mid p-0.5">
              <button
                :class="[
                  'px-3 py-1.5 text-xs rounded-sm transition-all duration-200',
                  !isLandscape
                    ? 'bg-neon/10 text-neon shadow-[0_0_8px_rgba(57,255,20,0.1)]'
                    : 'text-gray-500 hover:text-gray-300',
                ]"
                @click="isLandscape = false"
              >
                竖向
              </button>
              <button
                :class="[
                  'px-3 py-1.5 text-xs rounded-sm transition-all duration-200',
                  isLandscape
                    ? 'bg-volt/15 text-volt shadow-[0_0_10px_rgba(180,77,255,0.15)]'
                    : 'text-gray-500 hover:text-gray-300',
                ]"
                @click="isLandscape = true"
              >
                横向
              </button>
            </div>
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
           预览打印效果
           ═══════════════════════════════════════════════ -->
      <section v-if="canSubmit && !showSuccess" class="animate-slide-up mb-4" style="animation-delay: 0.15s">
        <button
          :disabled="isPreviewing || isSubmitting"
          class="btn-cyber group w-full border border-cyan/30 bg-cyan/5 text-cyan transition-all hover:border-cyan/50 hover:bg-cyan/10 active:scale-[0.98] disabled:opacity-30 disabled:cursor-not-allowed"
          @click="handlePreview"
        >
          <span v-if="!isPreviewing" class="flex items-center justify-center gap-2 text-xs uppercase tracking-wider">
            <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round"
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path stroke-linecap="round" stroke-linejoin="round"
                d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
            预览打印效果
          </span>
          <span v-else class="flex items-center justify-center gap-2 text-xs">
            <span class="inline-block h-4 w-4 animate-spin rounded-full border-2 border-cyan/30 border-t-cyan" />
            正在生成预览...
          </span>
        </button>
      </section>

      <!-- ═══════════════════════════════════════════════
           打印预览面板
           ═══════════════════════════════════════════════ -->
      <section v-if="previewBlobUrl && !showSuccess" class="animate-slide-up mb-6">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-cyan">
            <span class="inline-block h-3 w-3 rounded-sm border border-cyan/40 bg-cyan/10" />
            打印效果预览
          </h2>
          <span class="text-[9px] text-gray-500">
            {{ printConfigLabel }}
          </span>
        </div>
        <div class="cyber-panel overflow-hidden">
          <div class="border-b border-cyber-border/50 px-4 py-2.5 flex items-center justify-between">
            <span class="text-[10px] text-gray-500 uppercase tracking-wider">
              {{ inputMode === 'file' && selectedFile ? selectedFile.name : '文本渲染结果' }}
            </span>
            <button
              class="text-[10px] text-gray-500 hover:text-red-400/70 transition-colors"
              @click="previewBlobUrl = null"
            >
              [ 关闭 ]
            </button>
          </div>
          <div class="bg-cyber-darkest p-2">
            <VuePdfEmbed
              v-if="previewBlobUrl"
              :source="previewBlobUrl"
              :page="1"
              class="max-w-full"
              :style="{ maxHeight: '55vh' }"
            />
          </div>
        </div>
      </section>

      <!-- ═══════════════════════════════════════════════
           提交按钮区
           ═══════════════════════════════════════════════ -->
      <section class="animate-slide-up" style="animation-delay: 0.2s">
        <button
          :disabled="!canSubmit || isSubmitting"
          class="btn-cyber group w-full"
          :class="[
            !canSubmit || isSubmitting
              ? 'bg-cyber-mid text-gray-600 border border-cyber-border cursor-not-allowed'
              : inputMode === 'text'
                ? 'bg-volt/10 text-volt border border-volt/30 hover:bg-volt/20 hover:border-volt/60 active:scale-[0.98]'
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
            {{ inputMode === 'text' ? '渲染并发送至云端' : '发送至云端队列' }}
          </span>

          <!-- 提交中文案 -->
          <span v-else class="flex items-center justify-center gap-2">
            <span class="inline-block h-4 w-4 animate-spin rounded-full border-2 border-neon/30 border-t-neon" />
            {{ inputMode === 'text' ? '正在渲染并发送...' : '正在发送至云端队列...' }}
          </span>

          <!-- 悬停发光条 -->
          <span
            v-if="canSubmit && !isSubmitting"
            :class="[
              'absolute inset-x-0 -bottom-px h-px bg-gradient-to-r opacity-0 transition-opacity group-hover:opacity-100',
              inputMode === 'text' ? 'from-transparent via-volt to-transparent' : 'from-transparent via-neon to-transparent',
            ]"
          />
        </button>

        <!-- 提交进度动画 -->
        <Transition name="progress">
          <div v-if="isSubmitting" class="mt-4 cyber-panel overflow-hidden p-4">
            <!-- 真实进度条 -->
            <div class="relative mb-3 h-1.5 overflow-hidden rounded-full bg-cyber-mid">
              <div
                v-if="inputMode === 'file'"
                class="h-full rounded-full transition-all duration-300"
                :style="{
                  width: submitProgress + '%',
                  background: 'linear-gradient(90deg, transparent, #39ff14, #b44dff, #39ff14, transparent)',
                  backgroundSize: '200% 100%',
                }"
              />
              <div
                v-else
                class="h-full animate-pulse rounded-full bg-volt/60"
                style="width: 100%"
              />
            </div>

            <!-- 进度百分比 -->
            <p class="mb-2 text-center font-mono text-sm text-neon tabular-nums">
              {{ inputMode === 'file' ? submitProgress + '%' : '渲染中...' }}
            </p>

            <!-- 状态文字流 -->
            <div class="flex flex-col gap-1 font-mono text-[10px]">
              <p class="flex items-center gap-2 text-neon/80">
                <span class="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-neon" />
                <span class="animate-pulse">{{ submittingMessages[currentMessageIndex] }}</span>
              </p>
              <template v-if="inputMode === 'file'">
                <p class="text-gray-600">
                  > uploading...
                  <span class="text-neon/40">{{ submitProgress }}%</span>
                </p>
                <p class="text-gray-600">
                  > connecting to starfire://cloud-node
                </p>
                <p class="flex items-center gap-1 text-gray-600">
                  <span class="inline-block h-1 w-1 rounded-full bg-cyan/50" />
                  transferring to cloud queue...
                </p>
                <p v-if="submitProgress >= 80" class="flex items-center gap-1 text-gray-600">
                  <span class="inline-block h-1 w-1 rounded-full bg-volt/50" />
                  processing on server...
                </p>
              </template>
              <template v-else>
                <p class="flex items-center gap-1 text-gray-600">
                  <span class="inline-block h-1 w-1 animate-pulse rounded-full bg-cyan/50" />
                  > converting Markdown + LaTeX to PDF...
                </p>
                <p class="flex items-center gap-1 text-gray-600">
                  <span class="inline-block h-1 w-1 rounded-full bg-volt/50" />
                  pushing to print queue...
                </p>
              </template>
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
        <button
          class="mt-3 text-[10px] uppercase tracking-wider text-gray-600 hover:text-cyan/60 transition-colors"
          @click="router.push('/history')"
        >
          [ 打印历史 ]
        </button>
      </footer>
    </main>
  </div>
</template>

<!-- ═══════════════════════════════════════════════════════════════════
     SCRIPT
     ═══════════════════════════════════════════════════════════════════ -->
<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { uploadPrintJob, uploadText, previewFile, previewText, extractText } from '@/composables/useApi'
import PrintPreview from '@/components/PrintPreview.vue'
import MarkdownPreview from '@/components/MarkdownPreview.vue'
import VuePdfEmbed from 'vue-pdf-embed'
import { ALLOWED_FILE_TYPES, ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB } from '@/utils/constants'

// ── 路由 ──
const route = useRoute()
const router = useRouter()

// ── 节点 ID (从 URL ?node=xxx 读取) ──
const nodeId = ref(route.query.node || null)

// ── 输入模式: file | text ──
const inputMode = ref('file')

// ── 文本编辑内容 ──
const textContent = ref('')

// ── 工具栏按钮 ──
const toolbarButtons = [
  { label: 'B',  title: '粗体',       insert: '**text**' },
  { label: 'I',  title: '斜体',       insert: '*text*' },
  { label: 'H1', title: '一级标题',   insert: '# ' },
  { label: 'H2', title: '二级标题',   insert: '## ' },
  { label: 'H3', title: '三级标题',   insert: '### ' },
  { label: '`',  title: '行内代码',   insert: '`text`' },
  { label: '```',title: '代码块',     insert: '\n```\n\n```\n' },
  { label: '>',  title: '引用',       insert: '> ' },
  { label: '-',  title: '无序列表',   insert: '- ' },
  { label: '1.', title: '有序列表',   insert: '1. ' },
  { label: '$',  title: '行内公式',   insert: '$x^2$' },
  { label: '$$', title: '块级公式',   insert: '\n$$\nE=mc^2\n$$\n' },
  { label: '--', title: '分隔线',     insert: '\n---\n' },
  { label: 'link', title: '链接',     insert: '[text](url)' },
  { label: '|',  title: '表格',       insert: '\n| col1 | col2 |\n|------|------|\n| a    | b    |\n' },
]

// ── 是否可以提交 ──
const canSubmit = computed(() => {
  if (inputMode.value === 'file') return !!selectedFile.value
  return textContent.value.trim().length > 0
})

// ── 构建通用 header_info (三个字段) ──
function buildHeaderInfo() {
  return {
    subject: headerInfo.subject,
    class_name: headerInfo.className,
    school_label: headerInfo.schoolLabel,
  }
}

// ═══════════════════════════════════════════════════════════
// 响应式状态
// ═══════════════════════════════════════════════════════════

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
  orientation: 'portrait', // 方向
  copies: 1,           // 份数
  media_source: 'auto', // 纸盒
})

// AI 摘要
const aiSummary = ref(false)

// 提交状态
const isSubmitting = ref(false)
const submitProgress = ref(0)
const showSuccess = ref(false)
const submittedJobId = ref('')
const errorMessage = ref('')

// 使用信息 (页首)
const headerInfo = reactive({
  subject: '',      // 科目
  className: '',    // 班级
  schoolLabel: '',  // 校级标识
})

// 预览状态
const isPreviewing = ref(false)
const previewBlobUrl = ref(null)

// 打印配置摘要 (显示在预览面板)
const printConfigLabel = computed(() => {
  const parts = [`${printOptions.copies || 1}份`]
  if (printOptions.number_up > 1) parts.push(`${printOptions.number_up}-up`)
  if (printOptions.sides === 'two-sided-long-edge') parts.push('双面')
  else parts.push('单面')
  parts.push(printOptions.orientation === 'landscape' ? '横向' : '竖向')
  parts.push(printOptions.media)
  return parts.join(' · ')
})

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

const isLandscape = computed({
  get: () => printOptions.orientation === 'landscape',
  set: (val) => {
    printOptions.orientation = val ? 'landscape' : 'portrait'
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

const trayOptions = [
  { label: '自动', value: 'auto' },
  { label: '纸盒1', value: 'tray-1' },
  { label: '纸盒2', value: 'tray-2' },
  { label: '纸盒3', value: 'tray-3' },
  { label: '手送', value: 'manual' },
]

// ── 在线编辑标记 (上传 DOCX/TXT 后自动切换到文本编辑) ──
const hasExtractedText = ref(false)

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
  hasExtractedText.value = false
}

// ── 在线编辑: 判断文件是否可提取文本 ──
const EXTRACTABLE_EXTS = ['.doc', '.docx', '.txt']
function isExtractable(file) {
  if (!file) return false
  return EXTRACTABLE_EXTS.some(ext => file.name.toLowerCase().endsWith(ext))
}

// ── 提取文本并切换到在线编辑 ──
const isExtractingText = ref(false)
async function handleExtractAndEdit() {
  if (!selectedFile.value || isExtractingText.value) return
  isExtractingText.value = true
  try {
    const result = await extractText(selectedFile.value)
    if (result.text) {
      textContent.value = result.text
      inputMode.value = 'text'
      hasExtractedText.value = true
    }
  } catch (err) {
    errorMessage.value = '文本提取失败: ' + (err.response?.data?.detail || err.message)
  } finally {
    isExtractingText.value = false
  }
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

// ── 预览打印效果 ──
async function handlePreview() {
  if (!canSubmit.value || isPreviewing.value) return

  isPreviewing.value = true
  previewBlobUrl.value = null

  try {
    const cupsOptions = {
      media: printOptions.media,
      number_up: printOptions.number_up,
      sides: printOptions.sides,
      orientation: printOptions.orientation,
      copies: printOptions.copies,
      media_source: printOptions.media_source,
      header_info: buildHeaderInfo(),
    }

    let url
    if (inputMode.value === 'file') {
      url = await previewFile(selectedFile.value, cupsOptions)
    } else {
      url = await previewText(textContent.value, cupsOptions)
    }
    previewBlobUrl.value = url
  } catch (err) {
    errorMessage.value = '预览生成失败: ' + (err.response?.data?.detail || err.message)
  } finally {
    isPreviewing.value = false
  }
}

// ═══════════════════════════════════════════════════════════════
// 提交逻辑
// ═══════════════════════════════════════════════════════════════

async function handleSubmit() {
  if (!canSubmit.value || isSubmitting.value) return

  isSubmitting.value = true
  showSuccess.value = false
  errorMessage.value = ''
  submitProgress.value = 0

  // 启动进度文案动画
  startSubmitAnimation()

  try {
    // 构建 CUPS 参数
    const cupsOptions = {
      media: printOptions.media,
      number_up: printOptions.number_up,
      sides: printOptions.sides,
      orientation: printOptions.orientation,
      copies: printOptions.copies,
      media_source: printOptions.media_source,
      header_info: buildHeaderInfo(),
    }

    let response

    if (inputMode.value === 'file') {
      // ── 文件上传 ──
      response = await uploadPrintJob(
        selectedFile.value,
        cupsOptions,
        aiSummary.value,
        nodeId.value,
        (pct) => { submitProgress.value = pct },
      )
    } else {
      // ── 文本提交 ──
      response = await uploadText(
        textContent.value,
        cupsOptions,
        aiSummary.value,
        nodeId.value,
      )
    }

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

// ── Markdown 工具栏插入 ──
function insertMarkdown(template) {
  const textarea = document.querySelector('textarea')
  if (!textarea) return

  const start = textarea.selectionStart
  const end = textarea.selectionEnd
  const selected = textContent.value.substring(start, end)

  let insertion = template
  // 如果选中了文字, 包裹它 (如选中 "hello" 按 B → **hello**)
  if (selected && template.includes('text')) {
    insertion = template.replace('text', selected)
  }

  // 块级插入在首行 (如 ##, >, ```)
  const isBlockTemplate = template.startsWith('\n') || template.startsWith('#') || template.startsWith('>') || template.startsWith('-') || template.startsWith('1.') || template.startsWith('|')
  if (isBlockTemplate && start > 0) {
    // 确保在新行开始
    const before = textContent.value.substring(0, start)
    if (!before.endsWith('\n') && before.length > 0) {
      insertion = '\n' + insertion
    }
  }

  textContent.value = textContent.value.substring(0, start) + insertion + textContent.value.substring(end)

  // 恢复光标位置
  nextTick(() => {
    const newPos = start + insertion.length
    textarea.focus()
    textarea.setSelectionRange(newPos, newPos)
  })
}

function startSubmitAnimation() {
  // 文案轮播
  messageTimer = setInterval(() => {
    currentMessageIndex.value = (currentMessageIndex.value + 1) % submittingMessages.length
  }, 2000)
}

function stopSubmitAnimation() {
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

/* ── 移动端触摸优化 ── */
@media (pointer: coarse) {
  /* 触摸设备增大可点击区域 */
  .cyber-panel.cursor-pointer {
    min-height: 120px;
  }
  /* 移除 tap 高亮 */
  button, [role="switch"], .cyber-panel.cursor-pointer {
    -webkit-tap-highlight-color: transparent;
    -webkit-touch-callout: none;
    user-select: none;
  }
  /* 增大按钮触摸区域 */
  button[class*="px-3"] {
    min-width: 36px;
    min-height: 36px;
  }
  /* 触摸按下反馈 */
  button:active:not(:disabled) {
    filter: brightness(1.3);
  }
}
</style>
