import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'
import fs from 'node:fs'
import path from 'node:path'

export default defineConfig({
  plugins: [
    vue(),
    // 生产构建时复制 pdf.worker 到 public 目录
    {
      name: 'copy-pdf-worker',
      writeBundle() {
        const src = path.resolve('node_modules/pdfjs-dist/build/pdf.worker.min.js')
        const dest = path.resolve('dist/pdf.worker.min.js')
        if (fs.existsSync(src)) {
          fs.copyFileSync(src, dest)
        }
      },
    },
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('pdfjs-dist')) {
            return 'pdfjs'
          }
        },
      },
    },
  },
  optimizeDeps: {
    include: ['pdfjs-dist'],
  },
})
