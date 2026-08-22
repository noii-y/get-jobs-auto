import { useState, useEffect } from 'react'
import { resultsApi } from '../api/client'
import { CheckCircle, XCircle, SkipForward, TrendingUp, FileText, FileSpreadsheet, Clock } from 'lucide-react'

const PLATFORM_LABELS: Record<string, string> = {
  boss: 'Boss直聘',
  job51: '51job',
  zhilian: '智联招聘',
  liepin: '猎聘',
}

const PLATFORM_COLORS: Record<string, string> = {
  boss: 'bg-green-500',
  job51: 'bg-blue-500',
  zhilian: 'bg-orange-500',
  liepin: 'bg-purple-500',
}

export default function Results() {
  const [results, setResults] = useState<any[]>([])
  const [stats, setStats] = useState<any>(null)
  const [trend, setTrend] = useState<any>(null)
  const [filter, setFilter] = useState({ platform: '', status: '' })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [filter])

  const loadData = async () => {
    setLoading(true)
    try {
      const [res, statsRes, trendRes] = await Promise.all([
        resultsApi.list({ ...filter, limit: 100 }),
        resultsApi.stats({ days: 7 }),
        resultsApi.trend({ days: 7 }),
      ])
      setResults(res.data.items)
      setStats(statsRes.data)
      setTrend(trendRes.data)
    } catch (error) {
      console.error('加载结果失败', error)
    } finally {
      setLoading(false)
    }
  }

  const handleExport = (format: 'csv' | 'excel') => {
    const params = new URLSearchParams()
    if (filter.platform) params.append('platform', filter.platform)
    if (filter.status) params.append('status', filter.status)
    const url = `/api/results/export/${format}?${params.toString()}`
    window.open(url, '_blank')
  }

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      success: 'bg-green-100 text-green-700',
      failed: 'bg-red-100 text-red-700',
      skipped: 'bg-amber-100 text-amber-700',
    }
    const labels: Record<string, string> = {
      success: '成功',
      failed: '失败',
      skipped: '跳过',
    }
    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${styles[status] || 'bg-slate-100'}`}>
        {labels[status] || status}
      </span>
    )
  }

  // 计算柱状图最大值
  const maxDaily = trend?.daily?.reduce((max: number, d: any) => Math.max(max, d.total), 0) || 1

  // 平台分布数据
  const platformData = stats?.by_platform || {}
  const platformTotal = Object.values(platformData).reduce((sum: number, p: any) => sum + p.total, 0) || 1

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-800">投递记录</h2>
        <p className="text-sm text-slate-500 mt-1">查看投递详情、趋势分析和统计数据</p>
      </div>

      {/* 统计概览 */}
      {stats && (
        <div className="grid grid-cols-4 gap-4">
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <div className="flex items-center gap-2 text-slate-500 text-xs mb-1">
              <TrendingUp className="w-3.5 h-3.5" />
              总投递
            </div>
            <p className="text-2xl font-bold text-slate-800">{stats.total}</p>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <div className="flex items-center gap-2 text-slate-500 text-xs mb-1">
              <CheckCircle className="w-3.5 h-3.5 text-green-500" />
              成功
            </div>
            <p className="text-2xl font-bold text-green-600">{stats.success}</p>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <div className="flex items-center gap-2 text-slate-500 text-xs mb-1">
              <XCircle className="w-3.5 h-3.5 text-red-500" />
              失败
            </div>
            <p className="text-2xl font-bold text-red-600">{stats.failed}</p>
          </div>
          <div className="bg-white rounded-lg border border-slate-200 p-4">
            <div className="flex items-center gap-2 text-slate-500 text-xs mb-1">
              <TrendingUp className="w-3.5 h-3.5" />
              成功率
            </div>
            <p className="text-2xl font-bold text-primary-600">{stats.success_rate}%</p>
          </div>
        </div>
      )}

      {/* 图表区域 */}
      {trend && (
        <div className="grid grid-cols-3 gap-4">
          {/* 投递趋势柱状图 */}
          <div className="col-span-2 bg-white rounded-lg border border-slate-200 p-4">
            <h3 className="text-sm font-medium text-slate-700 mb-4">近7天投递趋势</h3>
            <div className="flex items-end justify-between h-40 gap-2">
              {trend.daily?.map((d: any) => (
                <div key={d.date} className="flex-1 flex flex-col items-center">
                  <div className="w-full flex flex-col items-center justify-end h-32">
                    <div
                      className="w-full bg-primary-500 rounded-t transition-all hover:bg-primary-600 relative group"
                      style={{ height: `${(d.total / maxDaily) * 100}%`, minHeight: d.total > 0 ? '4px' : '0' }}
                    >
                      <div className="absolute -top-6 left-1/2 -translate-x-1/2 text-xs text-slate-600 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                        {d.total}个
                      </div>
                    </div>
                  </div>
                  <span className="text-xs text-slate-400 mt-2">{d.date.slice(5)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* 平台分布 + 最佳时间 */}
          <div className="space-y-4">
            {/* 平台分布 */}
            <div className="bg-white rounded-lg border border-slate-200 p-4">
              <h3 className="text-sm font-medium text-slate-700 mb-3">平台分布</h3>
              <div className="space-y-2">
                {Object.entries(platformData).map(([platform, data]: [string, any]) => (
                  <div key={platform}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-slate-600">{PLATFORM_LABELS[platform] || platform}</span>
                      <span className="text-slate-400">{data.total} ({Math.round(data.total / platformTotal * 100)}%)</span>
                    </div>
                    <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${PLATFORM_COLORS[platform] || 'bg-slate-500'}`}
                        style={{ width: `${(data.total / platformTotal) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
                {Object.keys(platformData).length === 0 && (
                  <p className="text-xs text-slate-400 text-center py-4">暂无数据</p>
                )}
              </div>
            </div>

            {/* 最佳投递时间 */}
            <div className="bg-white rounded-lg border border-slate-200 p-4">
              <h3 className="text-sm font-medium text-slate-700 mb-3 flex items-center gap-1">
                <Clock className="w-3.5 h-3.5" />
                最佳投递时段
              </h3>
              {trend.best_hours?.length > 0 ? (
                <div className="space-y-2">
                  {trend.best_hours.map((h: any) => (
                    <div key={h.hour} className="flex items-center justify-between text-xs">
                      <span className="text-slate-600">{h.hour}:00 - {h.hour + 1}:00</span>
                      <span className="text-green-600 font-medium">{h.success_rate}%</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 text-center py-2">数据不足，多投几次后显示</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 筛选器 */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex gap-3">
          <select
            value={filter.platform}
            onChange={e => setFilter({ ...filter, platform: e.target.value })}
            className="px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">全部平台</option>
            <option value="boss">Boss直聘</option>
            <option value="job51">51job</option>
            <option value="zhilian">智联招聘</option>
            <option value="liepin">猎聘</option>
          </select>
          <select
            value={filter.status}
            onChange={e => setFilter({ ...filter, status: e.target.value })}
            className="px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="">全部状态</option>
            <option value="success">成功</option>
            <option value="failed">失败</option>
            <option value="skipped">跳过</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleExport('csv')}
            className="flex items-center gap-1.5 px-3 py-2 text-sm border border-slate-300 rounded-md hover:bg-slate-50 text-slate-600 transition-colors"
          >
            <FileText className="w-4 h-4" />
            导出CSV
          </button>
          <button
            onClick={() => handleExport('excel')}
            className="flex items-center gap-1.5 px-3 py-2 text-sm bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors"
          >
            <FileSpreadsheet className="w-4 h-4" />
            导出Excel
          </button>
        </div>
      </div>

      {/* 结果列表 */}
      <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
        <table className="w-full">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">职位</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">公司</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">薪资</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">城市</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">平台</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">状态</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">时间</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {loading ? (
              <tr><td colSpan={7} className="px-4 py-12 text-center text-slate-400">加载中...</td></tr>
            ) : results.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-12 text-center text-slate-400">暂无投递记录</td></tr>
            ) : (
              results.map((item: any) => (
                <tr key={item.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-sm text-slate-800 font-medium max-w-xs truncate">{item.job_title}</td>
                  <td className="px-4 py-3 text-sm text-slate-600">{item.company}</td>
                  <td className="px-4 py-3 text-sm text-slate-600">{item.salary || '-'}</td>
                  <td className="px-4 py-3 text-sm text-slate-600">{item.city || '-'}</td>
                  <td className="px-4 py-3 text-sm text-slate-500">
                    {PLATFORM_LABELS[item.platform] || item.platform}
                  </td>
                  <td className="px-4 py-3">{getStatusBadge(item.status)}</td>
                  <td className="px-4 py-3 text-sm text-slate-500">
                    {new Date(item.created_at).toLocaleString('zh-CN')}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
