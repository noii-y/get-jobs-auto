import { ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  Play, History, List, Ban, Settings, Zap, Clock, Layers,
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

  return (
    <div className="min-h-screen flex bg-slate-50 text-slate-800">
      {/* 侧边栏 */}
      <aside className="w-56 bg-white border-r border-slate-200 flex flex-col">
        {/* Logo */}
        <div className="h-16 flex items-center px-5 border-b border-slate-100">
          <div className="w-9 h-9 bg-primary-50 rounded-lg flex items-center justify-center mr-3">
            <Zap className="w-5 h-5 text-primary-600" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-slate-800 tracking-tight">Get Jobs Auto</h1>
            <p className="text-[10px] text-slate-400 font-medium uppercase tracking-wider">自动化求职</p>
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
                className={`group flex items-center px-5 py-2.5 text-sm transition-all duration-150 ${
                  isActive
                    ? 'bg-primary-50 text-primary-700 font-medium'
                    : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                }`}
              >
                {isActive && <div className="absolute left-0 w-1 h-8 bg-primary-600 rounded-r" />}
                <Icon className={`w-4 h-4 mr-3 transition-colors ${isActive ? 'text-primary-600' : 'text-slate-400 group-hover:text-slate-600'}`} />
                <span>{item.label}</span>
              </Link>
            )
          })}
        </nav>

        {/* 底部 */}
        <div className="p-4 border-t border-slate-100">
          <div className="flex items-center gap-2 mb-1.5">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            <span className="text-[11px] text-slate-500 font-medium">系统运行中</span>
          </div>
          <p className="text-[10px] text-slate-400">v1.1.1 · 4 平台已接入</p>
        </div>
      </aside>

      {/* 主内容区 */}
      <main className="flex-1 overflow-auto">
        <div className="p-6 max-w-7xl mx-auto">
          {children}
        </div>
      </main>
    </div>
  )
}
