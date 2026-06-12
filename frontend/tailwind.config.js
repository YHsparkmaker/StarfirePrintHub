/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      // ═══════════════════════════════════════════════════
      // Y2K Cyber Dawn 赛博配色方案
      // ═══════════════════════════════════════════════════
      colors: {
        // 底色
        cyber: {
          darkest:  '#0a0a0f',   // 最深背景
          dark:     '#0f0f1a',   // 卡片背景
          mid:      '#161625',   // 面板背景
          surface:  '#1a1a2e',   // 悬浮表面
          border:   '#2a2a4a',   // 边框
        },
        // 霓虹绿 — 主操作色
        neon: {
          DEFAULT:  '#39ff14',   // 标准霓虹绿
          glow:     '#39ff1480', // 发光 (半透明)
          soft:     '#39ff1440', // 柔光
          dim:      '#1a4a1a',   // 暗绿
        },
        // 电紫 — 强调色
        volt: {
          DEFAULT:  '#b44dff',   // 标准电紫
          glow:     '#b44dff80',
          soft:     '#b44dff40',
          dim:      '#3a1a5a',
        },
        // 青蓝 — 信息色
        cyan: {
          DEFAULT:  '#00e5ff',
          glow:     '#00e5ff80',
          soft:     '#00e5ff40',
        },
      },
      // ── 自定义字体 ──
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      // ── 自定义动画 ──
      animation: {
        'glow-pulse': 'glowPulse 2s ease-in-out infinite',
        'scan-line': 'scanLine 8s linear infinite',
        'float': 'float 3s ease-in-out infinite',
        'flicker': 'flicker 4s linear infinite',
        'slide-up': 'slideUp 0.4s ease-out',
        'data-stream': 'dataStream 2s linear infinite',
        'spin-slow': 'spin 4s linear infinite',
      },
      keyframes: {
        glowPulse: {
          '0%, 100%': { boxShadow: '0 0 5px var(--tw-shadow-color), 0 0 20px var(--tw-shadow-color)' },
          '50%': { boxShadow: '0 0 20px var(--tw-shadow-color), 0 0 60px var(--tw-shadow-color)' },
        },
        scanLine: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100vh)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-6px)' },
        },
        flicker: {
          '0%, 100%': { opacity: '1' },
          '92%': { opacity: '1' },
          '93%': { opacity: '0.3' },
          '94%': { opacity: '1' },
          '96%': { opacity: '0.6' },
          '97%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        dataStream: {
          '0%': { backgroundPosition: '0% 0%' },
          '100%': { backgroundPosition: '0% 200%' },
        },
      },
      // ── 背景图案 ──
      backgroundImage: {
        'grid-pattern': `
          linear-gradient(rgba(57, 255, 20, 0.03) 1px, transparent 1px),
          linear-gradient(90deg, rgba(57, 255, 20, 0.03) 1px, transparent 1px)
        `,
      },
      backgroundSize: {
        'grid': '32px 32px',
      },
    },
  },
  plugins: [],
}
