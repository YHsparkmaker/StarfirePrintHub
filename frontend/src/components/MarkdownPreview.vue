<!-- ═══════════════════════════════════════════════════════════════════
     MarkdownPreview.vue — 实时 Markdown + LaTeX 预览
     接收 markdownText prop → marked 解析 → katex 渲染数学公式
     ═══════════════════════════════════════════════════════════════════ -->
<template>
  <div v-if="hasContent" class="animate-slide-up">
    <!-- 区块标题 -->
    <div class="mb-3 flex items-center justify-between">
      <h2 class="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-cyan">
        <span class="inline-block h-3 w-3 rounded-sm border border-cyan/40 bg-cyan/10" />
        实时预览
      </h2>
      <button
        class="text-[10px] uppercase tracking-wider text-gray-500 hover:text-neon/70 transition-colors"
        :class="{ 'text-neon/50': visible }"
        @click="visible = !visible"
      >
        <span>{{ visible ? '[ − 收起 ]' : '[ + 展开 ]' }}</span>
      </button>
    </div>

    <Transition name="preview-expand">
      <div v-if="visible" class="cyber-panel overflow-hidden">
        <!-- 内容区 -->
        <div
          ref="previewEl"
          class="markdown-body max-h-[55vh] overflow-y-auto p-4 text-sm leading-relaxed"
        />
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, watch, computed, nextTick, onMounted } from 'vue'
import { marked } from 'marked'
import katex from 'katex'
import 'katex/dist/katex.min.css'

const props = defineProps({
  text: { type: String, default: '' },
  autoShow: { type: Boolean, default: true },
})

const visible = ref(true)
const previewEl = ref(null)
const hasContent = computed(() => props.text.trim().length > 0)

// ── marked 配置 ──
marked.setOptions({
  breaks: true,
  gfm: true,
})

// ── LaTeX 正则 ──
const LATEX_BLOCK = /\$\$([\s\S]*?)\$\$/g
const LATEX_INLINE = /\$(.*?)\$/g

function renderLaTeX(html) {
  // 块级公式
  html = html.replace(LATEX_BLOCK, (_, formula) => {
    try {
      return katex.renderToString(formula.trim(), {
        displayMode: true,
        throwOnError: false,
        output: 'html',
      })
    } catch {
      return `<pre>$$${formula}$$</pre>`
    }
  })
  // 行内公式
  html = html.replace(LATEX_INLINE, (match, formula) => {
    try {
      return katex.renderToString(formula.trim(), {
        displayMode: false,
        throwOnError: false,
        output: 'html',
      })
    } catch {
      return `<code>$${formula}$</code>`
    }
  })
  return html
}

async function updatePreview() {
  if (!previewEl.value) return

  const raw = props.text
  if (!raw.trim()) {
    previewEl.value.innerHTML = ''
    return
  }

  // 1. 保护 LaTeX 块 → 唯一占位符
  const latexBlocks = []
  let protectedText = raw

  // 保护 $$...$$ 块
  protectedText = protectedText.replace(LATEX_BLOCK, (match) => {
    const idx = latexBlocks.length
    latexBlocks.push(match)
    return `__LATEX_BLOCK_${idx}__`
  })

  // 保护 $...$ 行内
  protectedText = protectedText.replace(LATEX_INLINE, (match) => {
    const idx = latexBlocks.length
    latexBlocks.push(match)
    return `__LATEX_INLINE_${idx}__`
  })

  // 2. Markdown → HTML
  let html = marked.parse(protectedText)

  // 3. 还原 LaTeX
  latexBlocks.forEach((latex, idx) => {
    if (latex.startsWith('$$')) {
      const formula = latex.slice(2, -2)
      try {
        const rendered = katex.renderToString(formula.trim(), {
          displayMode: true,
          throwOnError: false,
          output: 'html',
        })
        html = html.replace(`__LATEX_BLOCK_${idx}__`, rendered)
      } catch {
        html = html.replace(`__LATEX_BLOCK_${idx}__`, `<pre class="text-red-400 text-xs py-2">LaTeX 渲染失败: ${escapeHtml(formula)}</pre>`)
      }
    } else {
      const formula = latex.slice(1, -1)
      try {
        const rendered = katex.renderToString(formula.trim(), {
          displayMode: false,
          throwOnError: false,
          output: 'html',
        })
        html = html.replace(`__LATEX_INLINE_${idx}__`, rendered)
      } catch {
        html = html.replace(`__LATEX_INLINE_${idx}__`, `<code class="text-red-400">${escapeHtml(formula)}</code>`)
      }
    }
  })

  previewEl.value.innerHTML = html
}

function escapeHtml(str) {
  const el = document.createElement('span')
  el.textContent = str
  return el.innerHTML
}

watch(() => props.text, () => nextTick(updatePreview), { immediate: false })
onMounted(() => nextTick(updatePreview))
</script>

<style scoped>
/* ── Markdown 内容样式 (赛博主题) ── */
.markdown-body :deep(h1) {
  font-size: 1.6em;
  font-weight: 700;
  color: #39ff14;
  border-bottom: 1px solid rgba(57,255,20,0.2);
  padding-bottom: 6px;
  margin: 1em 0 0.5em;
}
.markdown-body :deep(h2) {
  font-size: 1.3em;
  font-weight: 700;
  color: #b44dff;
  border-bottom: 1px solid rgba(180,77,255,0.15);
  padding-bottom: 4px;
  margin: 1em 0 0.5em;
}
.markdown-body :deep(h3) {
  font-size: 1.1em;
  font-weight: 600;
  color: #00e5ff;
  margin: 0.8em 0 0.4em;
}
.markdown-body :deep(p) {
  margin: 0.6em 0;
  color: #c4c4d0;
}
.markdown-body :deep(strong) {
  color: #39ff14;
}
.markdown-body :deep(a) {
  color: #00e5ff;
  text-decoration: underline;
}
.markdown-body :deep(code) {
  font-family: 'Courier New', monospace;
  background: rgba(30,30,46,0.8);
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 0.9em;
  color: #f5c2e7;
}
.markdown-body :deep(pre) {
  background: rgba(15,15,25,0.9);
  padding: 12px 16px;
  border-radius: 6px;
  overflow-x: auto;
  border: 1px solid rgba(57,255,20,0.1);
  margin: 0.8em 0;
}
.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
  color: #cdd6f4;
}
.markdown-body :deep(blockquote) {
  border-left: 3px solid rgba(57,255,20,0.3);
  padding: 4px 14px;
  margin: 0.8em 0;
  color: #888;
  background: rgba(57,255,20,0.03);
}
.markdown-body :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 12px 0;
  font-size: 0.92em;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid rgba(57,255,20,0.15);
  padding: 6px 12px;
  text-align: left;
}
.markdown-body :deep(th) {
  background: rgba(57,255,20,0.08);
  color: #39ff14;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 1.5em;
  color: #c4c4d0;
}
.markdown-body :deep(li) { margin: 2px 0; }
.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid rgba(57,255,20,0.1);
  margin: 1em 0;
}
.markdown-body :deep(.katex) {
  font-size: 1.05em;
  color: #e0e0e0;
}

/* ── 展开/收起动画 ── */
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
