import { useState, useEffect } from 'react'
import { runsApi } from '../api/client'
import { Clock, CheckCircle, XCircle, Loader2, StopCircle } from 'lucide-react'

export default function History() {
  const [runs, setRuns] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadRuns()
  }, [])

  const loadRuns = async () => {
    try {
      const response = await runsApi.list({ limit: 50 })
      setRuns(response.data)
    } catch (error) {
      console.error('加载历史失败', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusBadge = (status: string) => {
    const styles: Record<string, string> = {
      running: 'bg-primary/10 text-primary-300',
      completed: 'bg-success/10 text-success',
      failed: 'bg-error/10 text-error',
      stopped: 'bg-warning/10 text-warning',
      pending: 'bg-surface text-fg-mute',
    }
    const labels: Record<string, string> = {
      running: '运行中',
      completed: '已完成',
      failed: '失败',
      stopped: '已停止',
      pending: '等待中',
    }
    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${styles[status] || styles.pending}`}>
        {labels[status] || status}
      </span>
    )
  }

  const getPlatformLabel = (platform: string) => {
    const map: Record<string, string> = {
      boss: 'Boss直聘',
      job51: '51job',
      zhilian: '智联招聘',
      liepin: '猎聘',
    }
    return map[platform] || platform
  }

  if (loading) {
    return <div className="text-center py-12 text-fg-mute">加载中...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-fg">运行历史</h2>
          <p className="text-sm text-fg-mute mt-1">查看所有投递任务的运行记录</p>
        </div>
        <button
          onClick={loadRuns}
          className="px-3 py-1.5 text-sm bg-card border border-line rounded-md hover:bg-surface text-fg-dim"
        >
          刷新
        </button>
      </div>

      <div className="bg-card rounded-lg border border-line overflow-x-auto">
        <table className="w-full">
          <thead className="bg-surface border-b border-line">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-fg-mute uppercase">ID</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-fg-mute uppercase">平台</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-fg-mute uppercase">状态</th>
              <th className="px-4 py-3 text-center text-xs font-medium text-fg-mute uppercase">总计</th>
              <th className="px-4 py-3 text-center text-xs font-medium text-fg-mute uppercase">成功</th>
              <th className="px-4 py-3 text-center text-xs font-medium text-fg-mute uppercase">失败</th>
              <th className="px-4 py-3 text-center text-xs font-medium text-fg-mute uppercase">跳过</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-fg-mute uppercase">开始时间</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-fg-mute uppercase">结束时间</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line-subtle">
            {runs.length === 0 ? (
              <tr>
                <td colSpan={9} className="px-4 py-12 text-center text-fg-mute">
                  暂无运行记录
                </td>
              </tr>
            ) : (
              runs.map((run: any) => (
                <tr key={run.id} className="hover:bg-surface/40">
                  <td className="px-4 py-3 text-sm text-fg-dim">#{run.id}</td>
                  <td className="px-4 py-3 text-sm text-fg-dim">{getPlatformLabel(run.platform)}</td>
                  <td className="px-4 py-3">{getStatusBadge(run.status)}</td>
                  <td className="px-4 py-3 text-center text-sm text-fg-dim">{run.total_count}</td>
                  <td className="px-4 py-3 text-center text-sm text-green-600 font-medium">{run.success_count}</td>
                  <td className="px-4 py-3 text-center text-sm text-red-600">{run.failed_count}</td>
                  <td className="px-4 py-3 text-center text-sm text-amber-600">{run.skipped_count}</td>
                  <td className="px-4 py-3 text-sm text-fg-mute">
                    {new Date(run.started_at).toLocaleString('zh-CN')}
                  </td>
                  <td className="px-4 py-3 text-sm text-fg-mute">
                    {run.finished_at ? new Date(run.finished_at).toLocaleString('zh-CN') : '-'}
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
