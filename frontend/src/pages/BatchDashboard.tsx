import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Play, Square, Pause, Loader2, CheckCircle, XCircle,
  Zap, RefreshCw, Layers, Terminal, Activity, ChevronRight,
  Clock, MapPin, Briefcase, Building2, BarChart3,
  CheckCircle2, SkipForward
} from 'lucide-react'
import { batchApi, subscribeBatchEvents } from '../api/client'

interface PlatformStatus {
  platform: string
  run_id: number | null
  status: string
  current_page: number
  current_index: number
  current_total: number
  current_company: string
  current_job: string
  current_action: string
  total_count: number
  success_count: number
  failed_count: number
  skipped_count: number
  is_paused: boolean
}

interface BatchStatus {
  batch_id: number
  name: string
  keyword: string
  city: string
  status: string
  current_platform: string
  total_runs: number
  completed_runs: number
  platforms: PlatformStatus[]
  started_at: string | null
  finished_at: string | null
}

interface BatchHistory {
  id: number
  name: string
  keyword: string
  city: string
  status: string
  current_platform: string
  total_runs: number
  completed_runs: number
  platforms: string
  started_at: string | null
  finished_at: string | null
}

interface BatchResults {
  batch_id: number
  keyword: string
  city: string
  status: string
  summary: { total: number; success: number; failed: number; skipped: number }
  platforms: { platform: string; total: number; success: number; failed: number; skipped: number }[]
  recent_results: {
    id: number; platform: string; job_title: string; company: string
    salary: string; city: string; status: string; message: string; created_at: string | null
  }[]
}

interface LogEntry {
  id: number
  time: string
  platform: string
  message: string
  level: string
}

const PLATFORMS = [
  { value: 'boss', label: 'Boss直聘', color: '#10b981', bg: 'bg-success/10', border: 'border-success/40', text: 'text-success', dot: 'bg-success', bar: 'bg-success' },
  { value: 'job51', label: '51job', color: '#3b82f6', bg: 'bg-primary/10', border: 'border-primary/40', text: 'text-primary-300', dot: 'bg-primary-400', bar: 'bg-primary-500' },
  { value: 'zhilian', label: '智联招聘', color: '#f59e0b', bg: 'bg-warning/10', border: 'border-warning/40', text: 'text-warning', dot: 'bg-warning', bar: 'bg-warning' },
  { value: 'liepin', label: '猎聘', color: '#8b5cf6', bg: 'bg-violet-500/10', border: 'border-violet-500/40', text: 'text-violet-300', dot: 'bg-violet-500', bar: 'bg-violet-500' },
]

const getPlatformInfo = (value: string) => PLATFORMS.find(p => p.value === value) || PLATFORMS[0]

const CITIES = ['全国', '北京', '上海', '广州', '深圳', '杭州', '南京', '成都', '武汉', '西安', '苏州', '天津', '重庆', '长沙', '青岛', '郑州']

const statusLabel = (s: string) => ({
  running: '运行中', pending: '等待中', completed: '已完成',
  stopped: '已停止', failed: '失败', paused: '已暂停'
}[s] || s)

const statusBadgeClass = (s: string) => ({
  running: 'bg-success/10 text-success border-success/30',
  pending: 'bg-surface text-fg-mute border-line',
  completed: 'bg-primary/10 text-primary-300 border-primary/30',
  stopped: 'bg-surface text-fg-mute border-line',
  failed: 'bg-error/10 text-error border-error/30',
  paused: 'bg-warning/10 text-warning border-warning/30',
}[s] || 'bg-surface text-fg-mute border-line')

export default function BatchDashboard() {
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(['boss', 'zhilian', 'liepin', 'job51'])
  const [keyword, setKeyword] = useState('Python开发')
  const [city, setCity] = useState('全国')
  const [maxPages, setMaxPages] = useState(1)
  const [greeting, setGreeting] = useState('您好，我对这个职位很感兴趣，希望能有机会沟通。')
  const [enableCompanyCheck, setEnableCompanyCheck] = useState(true)

  const [batchStatus, setBatchStatus] = useState<BatchStatus | null>(null)
  const [batchResults, setBatchResults] = useState<BatchResults | null>(null)
  const [history, setHistory] = useState<BatchHistory[]>([])
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [isStarting, setIsStarting] = useState(false)
  const [isRunning, setIsRunning] = useState(false)

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const sseRef = useRef<(() => void) | null>(null)
  const logIdRef = useRef(0)
  const logsEndRef = useRef<HTMLDivElement>(null)

  const addLog = useCallback((platform: string, message: string, level: string = 'info') => {
    const now = new Date()
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`
    setLogs(prev => {
      const next = [...prev, { id: logIdRef.current++, time, platform, message, level }]
      return next.slice(-200) // 最多保留200条
    })
  }, [])

  const loadHistory = useCallback(async () => {
    try {
      const res = await batchApi.list({ limit: 10 })
      setHistory(res.data.items || [])
    } catch (e) { console.error('加载历史失败', e) }
  }, [])

  useEffect(() => { loadHistory() }, [loadHistory])

  // 自动滚动日志到底部
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const refreshStatus = useCallback(async (batchId: number) => {
    try {
      const res = await batchApi.get(batchId)
      setBatchStatus(res.data)
      return res.data
    } catch (e) {
      console.error('获取状态失败', e)
      return null
    }
  }, [])

  const loadResults = useCallback(async (batchId: number) => {
    try {
      const res = await batchApi.results(batchId)
      setBatchResults(res.data)
    } catch (e) { console.error('获取结果失败', e) }
  }, [])

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  const startSSE = useCallback((batchId: number) => {
    // 关闭旧连接
    if (sseRef.current) { sseRef.current(); sseRef.current = null }

    const unsub = subscribeBatchEvents(batchId, (data) => {
      const eventType = data.event_type
      const msg = data.message || ''
      const plat = data.platform || 'batch'

      // 处理实时状态事件：更新对应平台卡片
      if (eventType === 'realtime_status') {
        const d = data.data || {}
        setBatchStatus(prev => {
          if (!prev) return prev
          return {
            ...prev,
            platforms: prev.platforms.map(p => {
              if (p.platform === plat) {
                return {
                  ...p,
                  status: 'running',
                  current_page: d.current_page ?? p.current_page,
                  current_index: d.current_index ?? p.current_index,
                  current_total: d.current_total ?? p.current_total,
                  current_company: d.current_company ?? p.current_company,
                  current_job: d.current_job ?? p.current_job,
                  current_action: d.current_action ?? p.current_action,
                  is_paused: d.current_action === '已暂停',
                }
              }
              return p
            })
          }
        })
        return
      }

      // 处理批量任务级别事件
      if (eventType === 'batch_started') {
        addLog('batch', `批量任务已启动，共${(data.data?.platforms || []).length}个平台`, 'info')
        refreshStatus(batchId)
      } else if (eventType === 'batch_platform_started') {
        const d = data.data || {}
        const retryMsg = d.retry ? `（第${d.retry + 1}次尝试）` : ''
        addLog(d.platform || plat, `开始执行${retryMsg}`, 'info')
        refreshStatus(batchId)
      } else if (eventType === 'batch_platform_finished') {
        addLog(plat, msg, 'success')
        refreshStatus(batchId)
      } else if (eventType === 'batch_platform_failed') {
        addLog(plat, msg, 'error')
        refreshStatus(batchId)
      } else if (eventType === 'batch_platform_retry') {
        addLog(plat, msg, 'warn')
      } else if (eventType === 'batch_finished') {
        addLog('batch', `批量任务${data.data?.status || '结束'}`, data.data?.status === 'completed' ? 'success' : 'warn')
        setIsRunning(false)
        stopPolling()
        refreshStatus(batchId)
        loadResults(batchId)
        loadHistory()
      } else if (eventType === 'log') {
        // 各平台日志
        const level = data.data?.level || 'info'
        addLog(plat, msg.replace(/^\[(INFO|ERROR|WARN|DEBUG)\]\s*/i, ''), level)
      } else if (eventType === 'result') {
        const d = data.data || {}
        if (d.status === 'success') {
          addLog(plat, `✓ ${d.company || ''} - ${d.job_title || ''}`, 'success')
        } else if (d.status === 'failed') {
          addLog(plat, `✗ ${d.company || ''} - ${d.job_title || ''}: ${msg}`, 'error')
        } else if (d.status === 'skipped') {
          addLog(plat, `→ ${d.company || ''} - ${d.job_title || ''}: ${msg}`, 'skip')
        }
      } else if (eventType === 'error') {
        addLog(plat, msg, 'error')
      } else if (eventType === 'status') {
        if (msg === 'completed' || msg === 'failed') {
          addLog(plat, `任务${msg === 'completed' ? '完成' : '失败'}`, msg === 'completed' ? 'success' : 'error')
        }
      }
    }, () => {
      // SSE 错误：启动兜底轮询
      console.warn('SSE断开，使用轮询兜底')
    })

    sseRef.current = unsub
  }, [addLog, refreshStatus, loadResults, loadHistory, stopPolling])

  const handleStart = async () => {
    if (!keyword.trim()) { alert('请输入搜索关键词'); return }
    if (selectedPlatforms.length === 0) { alert('请至少选择一个平台'); return }
    setIsStarting(true)
    setBatchResults(null)
    setLogs([])
    try {
      const res = await batchApi.start({
        keyword, city, max_pages: maxPages, say_hi: greeting,
        enable_company_check: enableCompanyCheck, platforms: selectedPlatforms.join(','),
      })
      const batchId = res.data.batch_id
      setIsRunning(true)
      await refreshStatus(batchId)
      startSSE(batchId)
      // 兜底轮询：每5秒刷新一次完整状态（防止SSE遗漏）
      stopPolling()
      pollingRef.current = setInterval(() => refreshStatus(batchId), 5000)
      loadHistory()
    } catch (e: any) {
      alert('启动失败: ' + (e.response?.data?.detail || e.message))
    } finally { setIsStarting(false) }
  }

  const handleStop = async () => {
    if (!batchStatus) return
    if (!confirm('确定要停止整个批量任务吗？')) return
    try {
      await batchApi.stop(batchStatus.batch_id)
      addLog('batch', '正在停止批量任务...', 'warn')
      setTimeout(() => refreshStatus(batchStatus.batch_id), 1000)
    } catch (e) { console.error('停止失败', e) }
  }

  const handlePlatformAction = async (platform: string, action: 'pause' | 'resume' | 'stop') => {
    if (!batchStatus) return
    try {
      if (action === 'pause') {
        await batchApi.pausePlatform(batchStatus.batch_id, platform)
        addLog(platform, '已暂停', 'warn')
      } else if (action === 'resume') {
        await batchApi.resumePlatform(batchStatus.batch_id, platform)
        addLog(platform, '已继续', 'info')
      } else {
        await batchApi.stopPlatform(batchStatus.batch_id, platform)
        addLog(platform, '正在停止...', 'warn')
      }
      setTimeout(() => refreshStatus(batchStatus.batch_id), 500)
    } catch (e) { console.error('操作失败', e) }
  }

  const togglePlatform = (value: string) => {
    setSelectedPlatforms(prev => prev.includes(value) ? prev.filter(p => p !== value) : [...prev, value])
  }

  const toggleAll = () => {
    setSelectedPlatforms(prev => prev.length === PLATFORMS.length ? [] : PLATFORMS.map(p => p.value))
  }

  const viewHistoryBatch = (id: number) => {
    batchApi.get(id).then(res => {
      setBatchStatus(res.data)
      setBatchResults(null)
      if (res.data.status === 'running') {
        setIsRunning(true)
        startSSE(id)
        stopPolling()
        pollingRef.current = setInterval(() => refreshStatus(id), 5000)
      } else {
        setIsRunning(false)
        stopPolling()
        if (sseRef.current) { sseRef.current(); sseRef.current = null }
        loadResults(id)
      }
    }).catch(() => {})
  }

  useEffect(() => {
    return () => {
      stopPolling()
      if (sseRef.current) sseRef.current()
    }
  }, [stopPolling])

  const overallProgress = batchStatus ? (batchStatus.completed_runs / batchStatus.total_runs) * 100 : 0

  const logLevelClass = (level: string) => ({
    info: 'text-fg-mute',
    success: 'text-green-600',
    error: 'text-red-600',
    warn: 'text-amber-600',
    skip: 'text-fg-mute',
  }[level] || 'text-fg-mute')

  return (
    <div className="space-y-5">
      {/* 页面标题 */}
      <div className="flex items-end justify-between">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <div className="w-10 h-10 bg-gradient-to-br from-primary-500 to-primary-600 rounded-xl flex items-center justify-center shadow-lg shadow-primary-500/20">
              <Layers className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-fg tracking-tight">全平台一键投递</h1>
              <p className="text-xs text-fg-mute">统一配置 · 串行执行 · SSE实时监控 · 失败自动重试</p>
            </div>
          </div>
        </div>
        {isRunning && (
          <button
            onClick={handleStop}
            className="flex items-center gap-2 px-4 py-2 bg-card border border-error/40 text-error rounded-lg hover:bg-error/10 transition-colors text-sm font-medium"
          >
            <Square className="w-4 h-4" /> 终止全部
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 min-[900px]:grid-cols-12 gap-5">
        {/* 左侧：配置面板 */}
        <div className="min-[900px]:col-span-4 space-y-4">
          {/* 配置卡片 */}
          <div className="bg-card rounded-xl border border-line shadow-sm overflow-hidden">
            <div className="px-5 py-3.5 border-b border-line-subtle flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-primary-500" />
                <span className="text-sm font-semibold text-fg-dim">投递配置</span>
              </div>
              <span className="text-[10px] font-mono text-fg-mute uppercase tracking-wider">Config</span>
            </div>
            <div className="p-5 space-y-4">
              {/* 平台选择 */}
              <div>
                <div className="flex items-center justify-between mb-2.5">
                  <label className="text-xs font-medium text-fg-mute uppercase tracking-wider">目标平台</label>
                  <button onClick={toggleAll} className="text-xs text-primary-600 hover:text-primary-700 font-medium">
                    {selectedPlatforms.length === PLATFORMS.length ? '全不选' : '全选'}
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {PLATFORMS.map(p => {
                    const selected = selectedPlatforms.includes(p.value)
                    return (
                      <button
                        key={p.value}
                        onClick={() => togglePlatform(p.value)}
                        disabled={isRunning}
                        className={`relative p-3 text-left rounded-lg border-2 transition-all duration-200 ${
                          selected
                            ? `${p.bg} ${p.border} shadow-sm`
                            : 'bg-surface border-line-subtle opacity-50 hover:opacity-75'
                        } ${isRunning ? 'cursor-not-allowed' : 'cursor-pointer hover:shadow-md hover:-translate-y-0.5'}`}
                      >
                        {selected && <div className={`absolute top-0 left-0 right-0 h-1 ${p.bar} rounded-t-lg`} />}
                        <div className="flex items-center gap-2">
                          <div className={`w-2.5 h-2.5 rounded-full ${p.dot} ${selected ? 'animate-pulse' : ''}`} />
                          <span className={`text-sm font-medium ${selected ? 'text-fg' : 'text-fg-mute'}`}>{p.label}</span>
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* 关键词 */}
              <div>
                <label className="block text-xs font-medium text-fg-mute uppercase tracking-wider mb-1.5">搜索关键词</label>
                <div className="relative">
                  <Briefcase className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-fg-mute" />
                  <input
                    type="text" value={keyword} onChange={e => setKeyword(e.target.value)}
                    disabled={isRunning}
                    className="w-full pl-10 pr-3 py-2.5 bg-surface border border-line rounded-lg text-sm text-fg focus:bg-base-200 focus:border-primary-300 focus:ring-2 focus:ring-primary-100 outline-none transition-all disabled:opacity-50"
                    placeholder="职位关键词"
                  />
                </div>
              </div>

              {/* 城市 + 页数 */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-fg-mute uppercase tracking-wider mb-1.5">城市</label>
                  <div className="relative">
                    <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-fg-mute" />
                    <select
                      value={city} onChange={e => setCity(e.target.value)} disabled={isRunning}
                      className="w-full pl-10 pr-3 py-2.5 bg-surface border border-line rounded-lg text-sm text-fg focus:bg-base-200 focus:border-primary-300 focus:ring-2 focus:ring-primary-100 outline-none disabled:opacity-50 appearance-none cursor-pointer"
                    >
                      {CITIES.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-fg-mute uppercase tracking-wider mb-1.5">最大页数</label>
                  <input
                    type="number" value={maxPages} onChange={e => setMaxPages(Math.max(1, parseInt(e.target.value) || 1))}
                    min={1} max={10} disabled={isRunning}
                    className="w-full px-3 py-2.5 bg-surface border border-line rounded-lg text-sm text-fg font-mono focus:bg-base-200 focus:border-primary-300 focus:ring-2 focus:ring-primary-100 outline-none disabled:opacity-50"
                  />
                </div>
              </div>

              {/* 打招呼语 */}
              <div>
                <label className="block text-xs font-medium text-fg-mute uppercase tracking-wider mb-1.5">
                  打招呼语 <span className="text-fg-mute normal-case font-normal">// Boss/猎聘</span>
                </label>
                <textarea
                  value={greeting} onChange={e => setGreeting(e.target.value)} rows={2}
                  disabled={isRunning}
                  className="w-full px-3 py-2.5 bg-surface border border-line rounded-lg text-sm text-fg-dim resize-none focus:bg-base-200 focus:border-primary-300 focus:ring-2 focus:ring-primary-100 outline-none disabled:opacity-50"
                />
              </div>

              {/* 公司背调 */}
              <label className="flex items-center gap-2.5 cursor-pointer p-2.5 bg-surface rounded-lg border border-line-subtle hover:border-line transition-colors">
                <input
                  type="checkbox" checked={enableCompanyCheck}
                  onChange={e => setEnableCompanyCheck(e.target.checked)}
                  disabled={isRunning}
                  className="w-4 h-4 accent-primary-600 rounded"
                />
                <div className="flex-1">
                  <span className="text-sm text-fg-dim font-medium">公司背调过滤</span>
                  <p className="text-[11px] text-fg-mute">自动跳过高风险公司</p>
                </div>
                <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${enableCompanyCheck ? 'bg-green-100 text-green-700' : 'bg-surface text-fg-mute'}`}>
                  {enableCompanyCheck ? 'ON' : 'OFF'}
                </span>
              </label>

              {/* 启动按钮 */}
              <button
                onClick={handleStart}
                disabled={isStarting || isRunning}
                className="w-full py-3 bg-gradient-to-r from-primary-500 to-primary-600 hover:from-primary-600 hover:to-primary-700 text-white rounded-lg font-semibold text-sm transition-all duration-200 disabled:from-surface disabled:to-surface disabled:cursor-not-allowed flex items-center justify-center gap-2 shadow-lg shadow-primary-500/25 hover:shadow-primary-500/35 hover:-translate-y-0.5 active:translate-y-0"
              >
                {isStarting ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> 初始化中...</>
                ) : (
                  <><Zap className="w-4 h-4" /> 一键投递 · {selectedPlatforms.length} 个平台</>
                )}
              </button>
            </div>
          </div>

          {/* 任务概览 */}
          {batchStatus && (
            <div className="bg-card rounded-xl border border-line shadow-sm overflow-hidden">
              <div className="px-5 py-3.5 border-b border-line-subtle flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-primary-500" />
                  <span className="text-sm font-semibold text-fg-dim">任务概览</span>
                </div>
                <span className="text-[10px] font-mono text-fg-mute">#{batchStatus.batch_id}</span>
              </div>
              <div className="p-5 space-y-4">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-fg-mute">整体进度</span>
                    <span className="text-sm font-mono font-semibold text-fg-dim">{batchStatus.completed_runs}/{batchStatus.total_runs}</span>
                  </div>
                  <div className="h-2 bg-surface rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-primary-400 to-primary-600 rounded-full transition-all duration-500"
                      style={{ width: `${overallProgress}%` }}
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="bg-surface rounded-lg p-3 border border-line-subtle">
                    <div className="text-[10px] text-fg-mute uppercase tracking-wider mb-0.5">关键词</div>
                    <div className="text-sm text-fg-dim font-medium truncate">{batchStatus.keyword}</div>
                  </div>
                  <div className="bg-surface rounded-lg p-3 border border-line-subtle">
                    <div className="text-[10px] text-fg-mute uppercase tracking-wider mb-0.5">城市</div>
                    <div className="text-sm text-fg-dim font-medium">{batchStatus.city}</div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 右侧：状态面板 */}
        <div className="min-[900px]:col-span-8 space-y-4">
          {/* 实时状态 */}
          {batchStatus ? (
            <div className="bg-card rounded-xl border border-line shadow-sm overflow-hidden">
              <div className="px-5 py-3.5 border-b border-line-subtle flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${isRunning ? 'bg-green-500 animate-pulse' : 'bg-line'}`} />
                  <span className="text-sm font-semibold text-fg-dim">实时状态</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${statusBadgeClass(batchStatus.status)}`}>
                    {statusLabel(batchStatus.status)}
                  </span>
                </div>
                {isRunning && (
                  <span className="flex items-center gap-1.5 text-[11px] text-green-600 font-medium">
                    <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
                    SSE实时推送
                  </span>
                )}
              </div>
              <div className="p-5">
                <div className="grid grid-cols-2 gap-4">
                  {batchStatus.platforms.map((p) => {
                    const info = getPlatformInfo(p.platform)
                    const isActive = p.status === 'running'
                    const isDone = ['completed', 'failed', 'stopped'].includes(p.status)
                    const progress = p.current_total > 0 ? (p.current_index / p.current_total) * 100 : 0

                    return (
                      <div
                        key={p.platform}
                        className={`relative rounded-xl border-2 transition-all duration-300 overflow-hidden ${
                          isActive
                            ? `${info.bg} ${info.border} shadow-md`
                            : isDone ? 'bg-surface border-line-subtle' : 'bg-surface/50 border-line-subtle border-dashed'
                        }`}
                      >
                        {/* 左侧色条 */}
                        <div className={`absolute left-0 top-0 bottom-0 w-1 ${isActive ? info.bar : isDone ? 'bg-line' : 'bg-line'}`} />

                        <div className="p-4 pl-5">
                          {/* 头部 */}
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                              <div className={`w-2.5 h-2.5 rounded-full ${info.dot} ${isActive ? 'animate-pulse' : ''}`} />
                              <span className="text-sm font-bold text-fg">{info.label}</span>
                              {isActive && <Loader2 className="w-3.5 h-3.5 text-fg-mute animate-spin" />}
                              {isDone && p.status === 'completed' && <CheckCircle className="w-4 h-4 text-blue-500" />}
                              {isDone && p.status !== 'completed' && <XCircle className="w-4 h-4 text-fg-mute" />}
                            </div>
                            {isActive && (
                              <div className="flex items-center gap-1">
                                {p.is_paused ? (
                                  <button onClick={() => handlePlatformAction(p.platform, 'resume')}
                                    className="px-2.5 py-1 text-[11px] font-medium bg-success/15 text-success rounded-md hover:bg-success/25 transition-colors flex items-center gap-1">
                                    <Play className="w-3 h-3" /> 继续
                                  </button>
                                ) : (
                                  <button onClick={() => handlePlatformAction(p.platform, 'pause')}
                                    className="px-2.5 py-1 text-[11px] font-medium bg-warning/15 text-warning rounded-md hover:bg-warning/25 transition-colors flex items-center gap-1">
                                    <Pause className="w-3 h-3" /> 暂停
                                  </button>
                                )}
                                <button onClick={() => handlePlatformAction(p.platform, 'stop')}
                                  className="px-2.5 py-1 text-[11px] font-medium bg-error/15 text-error rounded-md hover:bg-error/25 transition-colors flex items-center gap-1">
                                  <Square className="w-3 h-3" /> 停止
                                </button>
                              </div>
                            )}
                            {p.status === 'pending' && (
                              <span className="text-[11px] text-fg-mute font-medium bg-surface px-2 py-0.5 rounded border border-line">排队中</span>
                            )}
                          </div>

                          {/* 当前操作 */}
                          <div className="flex items-center gap-2 mb-3">
                            {isActive ? (
                              <>
                                <span className="relative flex h-2 w-2">
                                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" style={{ backgroundColor: info.color }} />
                                  <span className="relative inline-flex rounded-full h-2 w-2" style={{ backgroundColor: info.color }} />
                                </span>
                                <span className="text-sm text-fg-dim font-medium">{p.current_action || '处理中...'}</span>
                              </>
                            ) : isDone ? (
                              <span className="text-sm text-fg-mute">{statusLabel(p.status)}</span>
                            ) : (
                              <span className="text-sm text-fg-mute italic">等待执行...</span>
                            )}
                          </div>

                          {/* 当前职位信息 */}
                          {isActive && (p.current_company || p.current_job) && (
                            <div className="bg-white/5 backdrop-blur rounded-lg p-3 mb-3 border border-line space-y-1.5">
                              {p.current_job && (
                                <div className="flex items-center gap-2 text-sm">
                                  <Briefcase className="w-3.5 h-3.5 text-fg-mute shrink-0" />
                                  <span className="text-fg-dim font-medium truncate">{p.current_job}</span>
                                </div>
                              )}
                              {p.current_company && (
                                <div className="flex items-center gap-2 text-sm">
                                  <Building2 className="w-3.5 h-3.5 text-fg-mute shrink-0" />
                                  <span className="text-fg-dim truncate">{p.current_company}</span>
                                </div>
                              )}
                              {p.current_page > 0 && (
                                <div className="flex items-center gap-2 text-xs font-mono text-fg-mute pt-1 border-t border-line-subtle">
                                  <Clock className="w-3 h-3" />
                                  第 {p.current_page} 页 · {p.current_index + 1}/{p.current_total || '?'}
                                </div>
                              )}
                            </div>
                          )}

                          {/* 进度条 */}
                          {isActive && p.current_total > 0 && (
                            <div className="h-1.5 bg-line rounded-full overflow-hidden mb-3">
                              <div className={`h-full ${info.bar} rounded-full transition-all duration-300`} style={{ width: `${progress}%` }} />
                            </div>
                          )}

                          {/* 统计 */}
                          <div className="flex items-center gap-4 text-xs">
                            <div className="flex items-center gap-1">
                              <span className="text-fg-mute">总计</span>
                              <span className="font-mono font-semibold text-fg-dim">{p.total_count}</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-green-500" />
                              <span className="text-fg-mute">成功</span>
                              <span className="font-mono font-semibold text-green-600">{p.success_count}</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                              <span className="text-fg-mute">失败</span>
                              <span className="font-mono font-semibold text-red-600">{p.failed_count}</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-line" />
                              <span className="text-fg-mute">跳过</span>
                              <span className="font-mono font-semibold text-fg-mute">{p.skipped_count}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </div>
          ) : (
            /* 空状态 */
            <div className="bg-card rounded-xl border border-line shadow-sm flex flex-col items-center justify-center py-20">
              <div className="w-16 h-16 bg-surface rounded-2xl flex items-center justify-center mb-4 border border-line-subtle">
                <Layers className="w-8 h-8 text-fg-mute" />
              </div>
              <p className="text-sm text-fg-mute mb-1 font-medium">暂无运行中的批量任务</p>
              <p className="text-xs text-fg-mute">在左侧配置参数后点击「一键投递」启动</p>
            </div>
          )}

          {/* 结果汇总 */}
          {batchResults && (
            <div className="bg-card rounded-xl border border-line shadow-sm overflow-hidden">
              <div className="px-5 py-3.5 border-b border-line-subtle flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-primary-500" />
                <span className="text-sm font-semibold text-fg-dim">投递结果汇总</span>
                <span className="text-[10px] font-mono text-fg-mute">#{batchResults.batch_id}</span>
              </div>
              <div className="p-5 space-y-4">
                {/* 总体统计 */}
                <div className="grid grid-cols-2 min-[900px]:grid-cols-4 gap-3">
                  <div className="bg-surface rounded-lg p-3 border border-line-subtle text-center">
                    <div className="text-2xl font-bold text-fg font-mono">{batchResults.summary.total}</div>
                    <div className="text-[11px] text-fg-mute mt-0.5">总计</div>
                  </div>
                  <div className="bg-success/10 rounded-lg p-3 border border-success/20 text-center">
                    <div className="text-2xl font-bold text-success font-mono">{batchResults.summary.success}</div>
                    <div className="text-[11px] text-success/70 mt-0.5">成功</div>
                  </div>
                  <div className="bg-error/10 rounded-lg p-3 border border-error/20 text-center">
                    <div className="text-2xl font-bold text-error font-mono">{batchResults.summary.failed}</div>
                    <div className="text-[11px] text-error/70 mt-0.5">失败</div>
                  </div>
                  <div className="bg-surface rounded-lg p-3 border border-line-subtle text-center">
                    <div className="text-2xl font-bold text-fg-mute font-mono">{batchResults.summary.skipped}</div>
                    <div className="text-[11px] text-fg-mute mt-0.5">跳过</div>
                  </div>
                </div>

                {/* 各平台统计 */}
                {batchResults.platforms.length > 0 && (
                  <div>
                    <div className="text-xs font-medium text-fg-mute uppercase tracking-wider mb-2">各平台明细</div>
                    <div className="space-y-2">
                      {batchResults.platforms.map(ps => {
                        const info = getPlatformInfo(ps.platform)
                        const rate = ps.total > 0 ? Math.round((ps.success / ps.total) * 100) : 0
                        return (
                          <div key={ps.platform} className="flex items-center gap-3 p-2.5 bg-surface rounded-lg">
                            <div className={`w-2 h-2 rounded-full ${info.dot}`} />
                            <span className="text-sm font-medium text-fg-dim w-20">{info.label}</span>
                            <div className="flex-1 h-1.5 bg-line rounded-full overflow-hidden">
                              <div className={`h-full ${info.bar} rounded-full`} style={{ width: `${rate}%` }} />
                            </div>
                            <div className="flex items-center gap-3 text-xs font-mono">
                              <span className="text-green-600">{ps.success}成功</span>
                              <span className="text-red-500">{ps.failed}失败</span>
                              <span className="text-fg-mute">{ps.skipped}跳过</span>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}

                {/* 最近投递明细 */}
                {batchResults.recent_results.length > 0 && (
                  <div>
                    <div className="text-xs font-medium text-fg-mute uppercase tracking-wider mb-2">最近投递</div>
                    <div className="max-h-60 overflow-y-auto border border-line-subtle rounded-lg">
                      <table className="w-full text-xs">
                        <thead className="bg-surface sticky top-0">
                          <tr>
                            <th className="text-left px-3 py-2 text-fg-mute font-medium">平台</th>
                            <th className="text-left px-3 py-2 text-fg-mute font-medium">职位</th>
                            <th className="text-left px-3 py-2 text-fg-mute font-medium">公司</th>
                            <th className="text-left px-3 py-2 text-fg-mute font-medium">状态</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-line-subtle">
                          {batchResults.recent_results.map(r => (
                            <tr key={r.id} className="hover:bg-surface">
                              <td className="px-3 py-2">
                                <span className={`inline-flex items-center gap-1 ${getPlatformInfo(r.platform).text}`}>
                                  <span className={`w-1.5 h-1.5 rounded-full ${getPlatformInfo(r.platform).dot}`} />
                                  {getPlatformInfo(r.platform).label}
                                </span>
                              </td>
                              <td className="px-3 py-2 text-fg-dim max-w-[200px] truncate">{r.job_title}</td>
                              <td className="px-3 py-2 text-fg-mute max-w-[150px] truncate">{r.company}</td>
                              <td className="px-3 py-2">
                                {r.status === 'success' && <span className="inline-flex items-center gap-1 text-green-600"><CheckCircle2 className="w-3 h-3" />成功</span>}
                                {r.status === 'failed' && <span className="inline-flex items-center gap-1 text-red-600"><XCircle className="w-3 h-3" />失败</span>}
                                {r.status === 'skipped' && <span className="inline-flex items-center gap-1 text-fg-mute"><SkipForward className="w-3 h-3" />跳过</span>}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 实时日志 */}
          {logs.length > 0 && (
            <div className="bg-card rounded-xl border border-line shadow-sm overflow-hidden">
              <div className="px-5 py-3.5 border-b border-line-subtle flex items-center gap-2">
                <Terminal className="w-4 h-4 text-fg-mute" />
                <span className="text-sm font-semibold text-fg-dim">实时日志</span>
                <span className="text-[10px] text-fg-mute font-mono">{logs.length}条</span>
              </div>
              <div className="p-3 max-h-64 overflow-y-auto bg-slate-900 font-mono text-xs leading-relaxed">
                {logs.map(log => (
                  <div key={log.id} className="flex gap-2 py-0.5">
                    <span className="text-fg-dim shrink-0">{log.time}</span>
                    <span className={`shrink-0 font-semibold ${
                      log.platform === 'batch' ? 'text-cyan-400' : getPlatformInfo(log.platform).text.replace('text-', 'text-').replace('700', '400')
                    }`}>[{log.platform === 'batch' ? 'BATCH' : getPlatformInfo(log.platform).label}]</span>
                    <span className={logLevelClass(log.level).replace('text-fg-mute', 'text-fg-mute').replace('text-green-600', 'text-green-400').replace('text-red-600', 'text-red-400').replace('text-amber-600', 'text-amber-400').replace('text-fg-mute', 'text-fg-mute')}>
                      {log.message}
                    </span>
                  </div>
                ))}
                <div ref={logsEndRef} />
              </div>
            </div>
          )}

          {/* 历史记录 */}
          <div className="bg-card rounded-xl border border-line shadow-sm overflow-hidden">
            <div className="px-5 py-3.5 border-b border-line-subtle flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4 text-fg-mute" />
                <span className="text-sm font-semibold text-fg-dim">任务历史</span>
              </div>
              <button onClick={loadHistory} className="flex items-center gap-1 text-xs text-fg-mute hover:text-fg-dim transition-colors">
                <RefreshCw className="w-3.5 h-3.5" /> 刷新
              </button>
            </div>
            <div className="divide-y divide-line-subtle">
              {history.length === 0 ? (
                <div className="p-10 text-center text-fg-mute text-sm">暂无历史记录</div>
              ) : (
                history.map(h => (
                  <div
                    key={h.id}
                    onClick={() => viewHistoryBatch(h.id)}
                    className="flex items-center justify-between px-5 py-3 hover:bg-surface cursor-pointer transition-colors group"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-xs font-mono text-fg-mute w-8">#{h.id}</span>
                      <ChevronRight className="w-3.5 h-3.5 text-fg-mute group-hover:text-primary-500 transition-colors" />
                      <span className="text-sm text-fg-dim font-medium">{h.keyword}</span>
                      <span className="text-xs text-fg-mute flex items-center gap-1">
                        <MapPin className="w-3 h-3" />{h.city}
                      </span>
                      <span className="text-xs text-fg-mute font-mono bg-surface px-1.5 py-0.5 rounded">{h.platforms}</span>
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="text-xs font-mono text-fg-mute">{h.completed_runs}/{h.total_runs}</span>
                      <span className={`text-[11px] px-2 py-0.5 rounded-full border font-medium ${statusBadgeClass(h.status)}`}>
                        {statusLabel(h.status)}
                      </span>
                      <span className="text-[11px] text-fg-mute font-mono">
                        {h.started_at ? new Date(h.started_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-'}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
