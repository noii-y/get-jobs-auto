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
        // 主色调（蓝色）
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
        // 工业风背景层级
        ink: {
          950: '#07090d',
          900: '#0d1117',
          850: '#121821',
          800: '#161d28',
          750: '#1c2430',
          700: '#232c3a',
          600: '#2d3748',
          500: '#3d4a5e',
        },
        // 文字层级
        chalk: {
          50: '#f1f5f9',
          100: '#e2e8f0',
          200: '#cbd5e1',
          300: '#94a3b8',
          400: '#64748b',
          500: '#475569',
        },
        // 平台专属色
        platform: {
          boss: '#10b981',
          job51: '#3b82f6',
          zhilian: '#f59e0b',
          liepin: '#a855f7',
        },
        // 状态色
        signal: {
          run: '#10b981',
          wait: '#64748b',
          done: '#3b82f6',
          stop: '#64748b',
          fail: '#ef4444',
          pause: '#f59e0b',
        },
        // 强调色（琥珀色，工业风常用）
        amber: {
          400: '#fbbf24',
          500: '#f59e0b',
          600: '#d97706',
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
        'glow-blue': '0 0 20px rgba(59, 130, 246, 0.15)',
        'glow-amber': '0 0 20px rgba(245, 158, 11, 0.15)',
        'glow-purple': '0 0 20px rgba(168, 85, 247, 0.15)',
        'inset-line': 'inset 0 1px 0 0 rgba(255,255,255,0.04)',
      },
    },
  },
  plugins: [],
}
