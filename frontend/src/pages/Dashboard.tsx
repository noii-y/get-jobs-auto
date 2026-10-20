import { useState, useRef, useEffect } from 'react'
import { Play, Square, Loader2, CheckCircle, XCircle, SkipForward, AlertCircle } from 'lucide-react'
import { runsApi, subscribeRunEvents } from '../api/client'

interface LogEntry {
  id: number
  type: string
  message: string
  timestamp: string
}

interface Stats {
  total: number
  success: number
  failed: number
  skipped: number
}

const PLATFORMS = [
  { value: 'boss', label: 'Boss直聘', color: 'bg-green-500' },
  { value: 'job51', label: '51job前程无忧', color: 'bg-blue-500' },
  { value: 'zhilian', label: '智联招聘', color: 'bg-orange-500' },
  { value: 'liepin', label: '猎聘', color: 'bg-purple-500' },
]

const getPlatformLabel = (value: string) => {
  return PLATFORMS.find(p => p.value === value)?.label || value
}

const CITIES = ['全国', '北京', '上海', '广州', '深圳', '杭州', '南京', '成都', '武汉', '西安', '苏州', '天津', '重庆', '长沙', '青岛', '郑州']

export default function Dashboard() {
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>(['boss'])
  const [keyword, setKeyword] = useState('Python开发')
  const [city, setCity] = useState('全国')
  const [salary, setSalary] = useState('')
  const [maxPages, setMaxPages] = useState(3)
  const [greeting, setGreeting] = useState('您好，我对这个职位很感兴趣，希望能有机会沟通。')
  const [useAI, setUseAI] = useState(false)
  const [filterInactiveHR, setFilterInactiveHR] = useState(true)
  const [hrActiveDays, setHrActiveDays] = useState(3)
  const [experience, setExperience] = useState('')
  const [degree, setDegree] = useState('')
  const [enableCompanyCheck, setEnableCompanyCheck] = useState(true)

  const [isRunning, setIsRunning] = useState(false)
  const [activeRunIds, setActiveRunIds] = useState<number[]>([])
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [stats, setStats] = useState<Stats>({ total: 0, success: 0, failed: 0, skipped: 0 })
  const [progress, setProgress] = useState({ current: 0, total: 0 })

  const logContainerRef = useRef<HTMLDivElement>(null)
  const logIdRef = useRef(0)
  const unsubscribesRef = useRef<Array<() => void>>([])

  // 自动滚动日志到底部
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop = logContainerRef.current.scrollHeight
    }
  }, [logs])

  const addLog = (type: string, message: string) => {
    logIdRef.current += 1
    setLogs(prev => [...prev.slice(-500), {
      id: logIdRef.current,
      type,
      message,
      timestamp: new Date().toLocaleTimeString(),
    }])
  }

  const handleStart = async () => {
    if (!keyword.trim()) {
      alert('请输入搜索关键词')
      return
    }

    try {
      setIsRunning(true)
      setLogs([])
      setStats({ total: 0, success: 0, failed: 0, skipped: 0 })
      logIdRef.current = 0
      unsubscribesRef.current = []

      const platformNames = selectedPlatforms.map(p => getPlatformLabel(p)).join('、')
      addLog('info', `正在启动 ${platformNames} 投递任务...`)

      const startedRunIds: number[] = []

      for (const plat of selectedPlatforms) {
        const response = await runsApi.start({
          platform: plat,
          keyword,
          city,
          salary,
          max_pages: maxPages,
          say_hi: greeting,
          use_ai: useAI,
          filter_inactive_hr: filterInactiveHR,
          hr_active_days: hrActiveDays,
          experience,
          degree,
          enable_company_check: enableCompanyCheck,
        })

        const runId = response.data.run_id
        startedRunIds.push(runId)
        const platName = getPlatformLabel(plat)
        addLog('success', `[${platName}] 任务已启动，运行ID: ${runId}`)

        // 订阅SSE事件
        const unsubscribe = subscribeRunEvents(
          runId,
          (data) => {
            if (data.event_type === 'log') {
              const level = data.data?.level || 'info'
              addLog(level, `[${platName}] ${data.message}`)
            } else if (data.event_type === 'result') {
              const status = data.data?.status
              if (status === 'success') {
                setStats(prev => ({ ...prev, success: prev.success + 1 }))
              } else if (status === 'failed') {
                setStats(prev => ({ ...prev, failed: prev.failed + 1 }))
              } else if (status === 'skipped') {
                setStats(prev => ({ ...prev, skipped: prev.skipped + 1 }))
              }
            } else if (data.event_type === 'status') {
              addLog('info', `[${platName}] 状态: ${data.message}`)
              if (data.message === 'completed' || data.message === 'failed') {
                // 检查是否所有任务都完成了
                const idx = startedRunIds.indexOf(runId)
                if (idx > -1) {
                  startedRunIds.splice(idx, 1)
                }
                if (startedRunIds.length === 0) {
                  setIsRunning(false)
                  setActiveRunIds([])
                  unsubscribesRef.current.forEach(u => u())
                  unsubscribesRef.current = []
                }
              }
            } else if (data.event_type === 'error') {
              addLog('error', `[${platName}] ${data.message}`)
            }
          },
          () => {
            addLog('warning', `[${platName}] 连接断开`)
          }
        )
        unsubscribesRef.current.push(unsubscribe)

        // 平台之间间隔2秒，避免浏览器冲突
        if (selectedPlatforms.indexOf(plat) < selectedPlatforms.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 2000))
        }
      }

      setActiveRunIds(startedRunIds)
    } catch (error: any) {
      addLog('error', `启动失败: ${error.response?.data?.detail || error.message}`)
      setIsRunning(false)
    }
  }

  const handleStop = async () => {
    if (activeRunIds.length === 0) return
    try {
      for (const runId of activeRunIds) {
        await runsApi.stop(runId)
      }
      addLog('warning', '正在停止所有任务...')
      setIsRunning(false)
      setActiveRunIds([])
      unsubscribesRef.current.forEach(u => u())
      unsubscribesRef.current = []
    } catch (error) {
      addLog('error', '停止失败')
    }
  }

  const getLogIcon = (type: string) => {
    switch (type) {
      case 'success': return <CheckCircle className="w-3.5 h-3.5 text-green-500 flex-shrink-0 mt-0.5" />
      case 'error': return <XCircle className="w-3.5 h-3.5 text-red-500 flex-shrink-0 mt-0.5" />
      case 'warning': return <AlertCircle className="w-3.5 h-3.5 text-warning flex-shrink-0 mt-0.5" />
      default: return <span className="w-3.5 h-3.5 flex-shrink-0" />
    }
  }

  const progressPercent = progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-fg">投递控制台</h2>
        <p className="text-sm text-fg-mute mt-1">配置投递参数，启动自动化投递任务</p>
      </div>

      <div className="grid grid-cols-1 min-[900px]:grid-cols-3 gap-6">
        {/* 左侧：配置表单 */}
        <div className="min-[900px]:col-span-1 space-y-4">
          <div className="bg-card rounded-lg border border-line p-5">
            <h3 className="text-sm font-semibold text-fg-dim mb-4">投递配置</h3>

            <div className="space-y-4">
              {/* 平台选择（多选） */}
              <div>
                <label className="block text-xs font-medium text-fg-dim mb-1.5">投递平台（可多选）</label>
                <div className="flex gap-2">
                  {PLATFORMS.map(p => (
                    <button
                      key={p.value}
                      onClick={() => {
                        if (selectedPlatforms.includes(p.value)) {
                          if (selectedPlatforms.length > 1) {
                            setSelectedPlatforms(selectedPlatforms.filter(x => x !== p.value))
                          }
                        } else {
                          setSelectedPlatforms([...selectedPlatforms, p.value])
                        }
                      }}
                      disabled={isRunning}
                      className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-colors ${
                        selectedPlatforms.includes(p.value)
                          ? 'bg-primary-600 text-white'
                          : 'bg-surface text-fg-dim hover:bg-surface-hover'
                      } disabled:opacity-50`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* 关键词 */}
              <div>
                <label className="block text-xs font-medium text-fg-dim mb-1.5">搜索关键词 *</label>
                <input
                  type="text"
                  value={keyword}
                  onChange={e => setKeyword(e.target.value)}
                  disabled={isRunning}
                  placeholder="如：Python开发、前端工程师"
                  className="w-full px-3 py-2 border border-line rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:opacity-60"
                />
              </div>

              {/* 城市 */}
              <div>
                <label className="block text-xs font-medium text-fg-dim mb-1.5">城市</label>
                <select
                  value={city}
                  onChange={e => setCity(e.target.value)}
                  disabled={isRunning}
                  className="w-full px-3 py-2 border border-line rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-60"
                >
                  {CITIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>

              {/* 薪资 */}
              <div>
                <label className="block text-xs font-medium text-fg-dim mb-1.5">薪资范围（可选）</label>
                <input
                  type="text"
                  value={salary}
                  onChange={e => setSalary(e.target.value)}
                  disabled={isRunning}
                  placeholder="如：10-15K（Boss直聘）"
                  className="w-full px-3 py-2 border border-line rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 disabled:opacity-60"
                />
              </div>

              {/* 最大页数 */}
              <div>
                <label className="block text-xs font-medium text-fg-dim mb-1.5">最大投递页数: {maxPages}</label>
                <input
                  type="range"
                  min="1"
                  max="10"
                  value={maxPages}
                  onChange={e => setMaxPages(Number(e.target.value))}
                  disabled={isRunning}
                  className="w-full accent-primary-600"
                />
                <p className="text-xs text-fg-mute mt-1">每页约15-20个职位</p>
              </div>

              {/* 打招呼语 */}
              <div>
                <label className="block text-xs font-medium text-fg-dim mb-1.5">默认打招呼语</label>
                <textarea
                  value={greeting}
                  onChange={e => setGreeting(e.target.value)}
                  disabled={isRunning}
                  rows={3}
                  className="w-full px-3 py-2 border border-line rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none disabled:opacity-60"
                />
              </div>

              {/* AI开关 */}
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-fg-dim">AI智能打招呼</p>
                  <p className="text-xs text-fg-mute">根据JD生成个性化问候</p>
                </div>
                <button
                  onClick={() => setUseAI(!useAI)}
                  disabled={isRunning}
                  className={`relative w-11 h-6 rounded-full transition-colors ${
                    useAI ? 'bg-primary-600' : 'bg-line'
                  } disabled:opacity-50`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                    useAI ? 'translate-x-5' : ''
                  }`} />
                </button>
              </div>

              {/* Boss直聘：不活跃HR过滤 + 高级过滤 */}
              {selectedPlatforms.includes('boss') && (
                <>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-fg-dim">过滤不活跃HR</p>
                      <p className="text-xs text-fg-mute">只投递近期活跃的招聘者</p>
                    </div>
                    <button
                      onClick={() => setFilterInactiveHR(!filterInactiveHR)}
                      disabled={isRunning}
                      className={`relative w-11 h-6 rounded-full transition-colors ${
                        filterInactiveHR ? 'bg-primary-600' : 'bg-line'
                      } disabled:opacity-50`}
                    >
                      <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                        filterInactiveHR ? 'translate-x-5' : ''
                      }`} />
                    </button>
                  </div>
                  {filterInactiveHR && (
                    <div>
                      <label className="text-xs text-fg-mute">活跃天数阈值</label>
                      <select
                        value={hrActiveDays}
                        onChange={(e) => setHrActiveDays(Number(e.target.value))}
                        disabled={isRunning}
                        className="mt-1 w-full px-3 py-1.5 text-sm border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                      >
                        <option value={1}>1天内</option>
                        <option value={3}>3天内</option>
                        <option value={7}>7天内</option>
                        <option value={14}>14天内</option>
                      </select>
                    </div>
                  )}

                  {/* 高级过滤：经验和学历 */}
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-xs text-fg-mute">工作经验</label>
                      <select
                        value={experience}
                        onChange={(e) => setExperience(e.target.value)}
                        disabled={isRunning}
                        className="mt-1 w-full px-3 py-1.5 text-sm border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                      >
                        <option value="">不限</option>
                        <option value="101">应届毕业生</option>
                        <option value="102">1年以下</option>
                        <option value="103">1-3年</option>
                        <option value="104">3-5年</option>
                        <option value="105">5-10年</option>
                        <option value="106">10年以上</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-xs text-fg-mute">学历要求</label>
                      <select
                        value={degree}
                        onChange={(e) => setDegree(e.target.value)}
                        disabled={isRunning}
                        className="mt-1 w-full px-3 py-1.5 text-sm border border-line rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                      >
                        <option value="">不限</option>
                        <option value="204">大专</option>
                        <option value="205">本科</option>
                        <option value="206">硕士</option>
                        <option value="207">博士</option>
                      </select>
                    </div>
                  </div>
                </>
              )}

              {/* 公司背调开关（所有平台通用） */}
              <div className="flex items-center justify-between pt-3 border-t border-line-subtle">
                <div>
                  <p className="text-sm font-medium text-fg-dim">公司背调</p>
                  <p className="text-xs text-fg-mute">自动检测高风险公司并跳过</p>
                </div>
                <button
                  onClick={() => setEnableCompanyCheck(!enableCompanyCheck)}
                  disabled={isRunning}
                  className={`relative w-11 h-6 rounded-full transition-colors ${
                    enableCompanyCheck ? 'bg-primary-600' : 'bg-line'
                  } disabled:opacity-50`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                    enableCompanyCheck ? 'translate-x-5' : ''
                  }`} />
                </button>
              </div>
            </div>

            {/* 启动/停止按钮 */}
            <div className="mt-5 pt-4 border-t border-line-subtle">
              {!isRunning ? (
                <button
                  onClick={handleStart}
                  className="w-full py-2.5 bg-primary-600 hover:bg-primary-700 text-white rounded-md text-sm font-medium flex items-center justify-center gap-2 transition-colors"
                >
                  <Play className="w-4 h-4" />
                  开始投递
                </button>
              ) : (
                <button
                  onClick={handleStop}
                  className="w-full py-2.5 bg-red-600 hover:bg-red-700 text-white rounded-md text-sm font-medium flex items-center justify-center gap-2 transition-colors"
                >
                  <Square className="w-4 h-4" />
                  停止投递
                </button>
              )}
            </div>
          </div>

          {/* 注意事项 */}
          <div className="bg-warning/10 border border-warning/30 rounded-lg p-4">
            <h4 className="text-sm font-medium text-warning mb-2">使用前请注意</h4>
            <ul className="text-xs text-fg-dim space-y-1 list-disc list-inside">
              <li>请先在Chrome浏览器中登录对应招聘平台</li>
              <li>Chrome需以调试模式启动（端口9222）</li>
              <li>建议控制投递频率，避免账号被限制</li>
              <li>运行期间请勿操作浏览器</li>
            </ul>
          </div>
        </div>

        {/* 右侧：实时日志和统计 */}
        <div className="min-[900px]:col-span-2 space-y-4">
          {/* 统计卡片 */}
          <div className="grid grid-cols-2 min-[900px]:grid-cols-4 gap-3">
            <StatCard label="总计" value={stats.total} icon={<Loader2 className="w-4 h-4" />} color="text-fg-mute" bg="bg-surface" />
            <StatCard label="成功" value={stats.success} icon={<CheckCircle className="w-4 h-4" />} color="text-success" bg="bg-success/15" />
            <StatCard label="失败" value={stats.failed} icon={<XCircle className="w-4 h-4" />} color="text-error" bg="bg-error/15" />
            <StatCard label="跳过" value={stats.skipped} icon={<SkipForward className="w-4 h-4" />} color="text-warning" bg="bg-warning/15" />
          </div>

          {/* 进度条 */}
          {isRunning && (
            <div className="bg-card rounded-lg border border-line p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-fg-dim">投递进度</span>
                <span className="text-sm text-fg-mute">{progress.current} / {progress.total || '?'}</span>
              </div>
              <div className="w-full h-2 bg-surface rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary-600 rounded-full transition-all duration-300"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
            </div>
          )}

          {/* 实时日志 */}
          <div className="bg-card rounded-lg border border-line overflow-hidden">
            <div className="px-4 py-3 border-b border-line-subtle flex items-center justify-between">
              <h3 className="text-sm font-semibold text-fg-dim">实时日志</h3>
              {isRunning && (
                <span className="flex items-center gap-1.5 text-xs text-green-600">
                  <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
                  运行中
                </span>
              )}
            </div>
            <div
              ref={logContainerRef}
              className="h-96 overflow-y-auto p-4 bg-slate-900 log-container"
            >
              {logs.length === 0 ? (
                <p className="text-fg-mute text-center py-8">暂无日志，点击"开始投递"启动任务</p>
              ) : (
                logs.map(log => (
                  <div key={log.id} className="flex gap-2 py-0.5">
                    <span className="text-fg-mute flex-shrink-0">[{log.timestamp}]</span>
                    {getLogIcon(log.type)}
                    <span className={`${
                      log.type === 'success' ? 'text-green-400' :
                      log.type === 'error' ? 'text-red-400' :
                      log.type === 'warning' ? 'text-amber-400' :
                      'text-fg-dim'
                    }`}>
                      {log.message}
                    </span>
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

function StatCard({ label, value, icon, color, bg }: {
  label: string
  value: number
  icon: React.ReactNode
  color: string
  bg: string
}) {
  return (
    <div className="bg-card rounded-lg border border-line p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-fg-mute">{label}</span>
        <span className={`${color} ${bg} p-1 rounded`}>{icon}</span>
      </div>
      <p className="text-2xl font-bold text-fg">{value}</p>
    </div>
  )
}
