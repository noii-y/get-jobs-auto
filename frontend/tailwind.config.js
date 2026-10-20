/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  safelist: [
    // 平台动态颜色类
    'border-platform-boss/40', 'border-platform-job51/40', 'border-platform-zhilian/40', 'border-platform-liepin/40',
    'border-platform-boss/50', 'border-platform-job51/50', 'border-platform-zhilian/50', 'border-platform-liepin/50',
    'bg-platform-boss', 'bg-platform-job51', 'bg-platform-zhilian', 'bg-platform-liepin',
    'text-platform-boss', 'text-platform-job51', 'text-platform-zhilian', 'text-platform-liepin',
    // 平台发光阴影
    'shadow-glow-green', 'shadow-glow-blue', 'shadow-glow-amber', 'shadow-glow-purple',
  ],
  theme: {
    extend: {
      colors: {
        // 主色：克制的靛蓝（Linear 风），只用于主按钮/选中态/聚焦
        primary: {
          50: '#161d2b',
          100: '#1e2839',
          200: '#2a3a55',
          300: '#6b9ce8',
          400: '#5aa0f5',
          500: '#4a96f5',
          600: '#3f93f7',
          700: '#2f7fe0',
          800: '#2566c0',
          900: '#1f4f94',
        },
        // 页面冷灰三层（靠明度分层次）
        base: {
          300: '#0d1115',
          200: '#14181c',
          100: '#191d23',
        },
        // 卡片/面板
        card: '#1e2227',
        // 可交互的次级表面
        surface: '#262b32',
        'surface-hover': '#30363e',
        // 细边框
        line: '#2b3038',
        'line-subtle': '#22262d',
        // 前景文字
        fg: {
          DEFAULT: '#eef1f5',
          dim: '#b6bbc3',
          mute: '#7b8189',
        },
        // 语义色（低饱和、暗底可读）
        success: '#3fbf86',
        warning: '#e1b75c',
        error: '#ef656b',
        // 平台专属色（hex，保留 /40 /50 透明度修饰）
        platform: {
          boss: '#10b981',
          job51: '#3b82f6',
          zhilian: '#f59e0b',
          liepin: '#a855f7',
        },
        // 冷灰阶（供 .panel 等旧组件复用）
        ink: {
          950: '#0d1115',
          900: '#11151a',
          850: '#14181c',
          800: '#191d23',
          750: '#1e2227',
          700: '#2b3038',
          600: '#3a4049',
          500: '#4a515a',
        },
        // 文字阶（供 .data-label / .data-value 等旧组件复用）
        chalk: {
          50: '#eef1f5',
          100: '#dfe3e9',
          200: '#c3c8cf',
          300: '#9aa0a9',
          400: '#7b8189',
          500: '#5f656d',
        },
        // 状态色
        signal: {
          run: '#3fbf86',
          wait: '#7b8189',
          done: '#3f93f7',
          stop: '#7b8189',
          fail: '#ef656b',
          pause: '#e1b75c',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'Consolas', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'scan': 'scan 2s linear infinite',
        'flow': 'flow 1.5s ease-in-out infinite',
        'blink': 'blink 1s step-end infinite',
      },
      keyframes: {
        scan: {
          '0%': { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(100%)' },
        },
        flow: {
          '0%, 100%': { opacity: '0.4' },
          '50%': { opacity: '1' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
      },
      boxShadow: {
        'glow-green': '0 0 20px rgba(16, 185, 129, 0.15)',
        'glow-blue': '0 0 20px rgba(63, 147, 247, 0.15)',
        'glow-amber': '0 0 20px rgba(225, 183, 92, 0.15)',
        'glow-purple': '0 0 20px rgba(168, 85, 247, 0.15)',
        'inset-line': 'inset 0 1px 0 0 rgba(255,255,255,0.04)',
      },
    },
  },
  plugins: [],
}
