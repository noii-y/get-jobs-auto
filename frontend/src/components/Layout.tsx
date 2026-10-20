import { ReactNode, useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  Play, History, List, Ban, Settings, Zap, Clock, Layers, Menu, X,
} from 'lucide-react'

interface LayoutProps {
  children: ReactNode
}

const navItems = [
  { path: '/', label: '单平台投递', icon: Play },
  { path: '/batch', label: '全平台一键投递', icon: Layers },
  { path: '/history', label: '运行历史', icon: History },
  { path: '/results', label: '投递记录', icon: List },
  { path: '/schedules', label: '定时任务', icon: Clock },
  { path: '/blacklist', label: '黑名单', icon: Ban },
  { path: '/settings', label: '设置', icon: Settings },
]

export default function Layout({ children }: LayoutProps) {
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)

  // 切换路由后自动收起移动端菜单
  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  return (
    <div className="min-h-screen flex flex-col min-[900px]:flex-row bg-base-100 text-fg">
      {/* 移动端顶部栏（窄屏） */}
      <header className="min-[900px]:hidden sticky top-0 z-40 h-14 flex items-center justify-between px-4 bg-base-200 border-b border-line">
        <div className="flex items-center">
          <div className="w-8 h-8 bg-primary-50 rounded-lg flex items-center justify-center mr-2.5">
            <Zap className="w-4 h-4 text-primary-600" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-fg tracking-tight">Get Jobs Auto</h1>
            <p className="text-[9px] text-fg-mute font-medium uppercase tracking-wider">自动化求职</p>
          </div>
        </div>
        <button
          onClick={() => setMenuOpen(o => !o)}
          className="p-2 rounded-md text-fg-dim hover:bg-surface"
          aria-label="菜单"
        >
          {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </header>

      {/* 移动端下拉菜单（窄屏） */}
      {menuOpen && (
        <div className="min-[900px]:hidden fixed inset-x-0 top-14 z-30 bg-base-200 border-b border-line shadow-lg max-h-[calc(100vh-3.5rem)] overflow-y-auto">
          <nav className="py-2">
            {navItems.map(item => {
              const Icon = item.icon
              const isActive = location.pathname === item.path
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center px-5 py-3 text-sm ${
                    isActive ? 'bg-primary-50 text-primary-300 font-medium' : 'text-fg-dim'
                  }`}
                >
                  <Icon className="w-4 h-4 mr-3" />
                  <span>{item.label}</span>
                </Link>
              )
            })}
          </nav>
          <div className="px-5 py-3 border-t border-line-subtle">
            <div className="flex items-center gap-2 mb-1.5">
              <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
              <span className="text-[11px] text-fg-mute font-medium">系统运行中</span>
            </div>
            <p className="text-[10px] text-fg-mute">4 平台已接入</p>
          </div>
        </div>
      )}

      {/* 桌面端侧边栏（≥900px） */}
      <aside className="hidden min-[900px]:flex w-56 bg-base-200 border-r border-line flex-col">
        {/* Logo */}
        <div className="h-16 flex items-center px-5 border-b border-line-subtle">
          <div className="w-9 h-9 bg-primary-50 rounded-lg flex items-center justify-center mr-3">
            <Zap className="w-5 h-5 text-primary-600" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-fg tracking-tight">Get Jobs Auto</h1>
            <p className="text-[10px] text-fg-mute font-medium uppercase tracking-wider">自动化求职</p>
          </div>
        </div>

        {/* 导航 */}
        <nav className="flex-1 py-3">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname === item.path
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`group relative flex items-center px-5 py-2.5 text-sm transition-all duration-150 ${
                  isActive
                    ? 'bg-primary-50 text-primary-300 font-medium'
                    : 'text-fg-dim hover:bg-surface hover:text-fg'
                }`}
              >
                {isActive && <div className="absolute left-0 w-1 h-8 bg-primary-600 rounded-r" />}
                <Icon className={`w-4 h-4 mr-3 transition-colors ${isActive ? 'text-primary-400' : 'text-fg-mute group-hover:text-fg-dim'}`} />
                <span>{item.label}</span>
              </Link>
            )
          })}
        </nav>

        {/* 底部 */}
        <div className="p-4 border-t border-line-subtle">
          <div className="flex items-center gap-2 mb-1.5">
            <div className="w-2 h-2 rounded-full bg-success animate-pulse" />
            <span className="text-[11px] text-fg-mute font-medium">系统运行中</span>
          </div>
          <p className="text-[10px] text-fg-mute">4 平台已接入</p>
        </div>
      </aside>

      {/* 主内容区 */}
      <main className="flex-1 overflow-auto">
        <div className="p-4 min-[900px]:p-6 max-w-7xl mx-auto">
          {children}
        </div>
      </main>
    </div>
  )
}
