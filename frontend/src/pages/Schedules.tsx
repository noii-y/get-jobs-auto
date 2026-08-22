import { useState, useEffect } from 'react'
import { schedulesApi } from '../api/client'
import { Plus, Clock, Trash2, Play, Pause, Calendar, Edit2, X, Check } from 'lucide-react'

const WEEKDAYS = [
  { value: '0', label: '一' },
  { value: '1', label: '二' },
  { value: '2', label: '三' },
  { value: '3', label: '四' },
  { value: '4', label: '五' },
  { value: '5', label: '六' },
  { value: '6', label: '日' },
]

const PLATFORMS = [
  { value: 'boss', label: 'Boss直聘' },
  { value: 'job51', label: '51job' },
  { value: 'zhilian', label: '智联招聘' },
  { value: 'liepin', label: '猎聘' },
]

const getPlatformLabel = (value: string) => {
  return PLATFORMS.find(p => p.value === value)?.label || value
}

interface Schedule {
  id: number
  name: string
  platform: string
  config: Record<string, any>
  run_time: string
  days_of_week: string
  enabled: boolean
  last_run_at: string | null
  last_run_status: string
  next_run_at: string | null
}

export default function Schedules() {
  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)

  // 表单状态
  const [form, setForm] = useState({
    name: '',
    platform: 'boss',
    keyword: 'Python开发',
    city: '全国',
    salary: '',
    max_pages: 5,
    say_hi: '您好，我对这个职位很感兴趣，希望能有机会沟通。',
    use_ai: false,
    filter_inactive_hr: true,
    hr_active_days: 3,
    experience: '',
    degree: '',
    enable_company_check: true,
    run_time: '09:00',
    days: ['0', '1', '2', '3', '4'],
    enabled: true,
  })

  useEffect(() => {
    loadSchedules()
  }, [])

  const loadSchedules = async () => {
    setLoading(true)
    try {
      const res = await schedulesApi.list()
      setSchedules(res.data.items)
    } catch (e) {
      console.error('加载定时任务失败', e)
    } finally {
      setLoading(false)
    }
  }

  const resetForm = () => {
    setForm({
      name: '',
      platform: 'boss',
      keyword: 'Python开发',
      city: '全国',
      salary: '',
      max_pages: 5,
      say_hi: '您好，我对这个职位很感兴趣，希望能有机会沟通。',
      use_ai: false,
      filter_inactive_hr: true,
      hr_active_days: 3,
      experience: '',
      degree: '',
      enable_company_check: true,
      run_time: '09:00',
      days: ['0', '1', '2', '3', '4'],
      enabled: true,
    })
    setEditingId(null)
  }

  const openCreate = () => {
    resetForm()
    setShowModal(true)
  }

  const openEdit = (sched: Schedule) => {
    setEditingId(sched.id)
    setForm({
      name: sched.name,
      platform: sched.platform,
      keyword: sched.config.keyword || '',
      city: sched.config.city || '全国',
      salary: sched.config.salary || '',
      max_pages: sched.config.max_pages || 5,
      say_hi: sched.config.say_hi || '',
      use_ai: sched.config.use_ai || false,
      filter_inactive_hr: sched.config.filter_inactive_hr ?? true,
      hr_active_days: sched.config.hr_active_days || 3,
      experience: sched.config.experience || '',
      degree: sched.config.degree || '',
      enable_company_check: sched.config.enable_company_check ?? true,
      run_time: sched.run_time,
      days: sched.days_of_week.split(',').filter(Boolean),
      enabled: sched.enabled,
    })
    setShowModal(true)
  }

  const handleSubmit = async () => {
    const config = {
      keyword: form.keyword,
      city: form.city,
      salary: form.salary,
      max_pages: form.max_pages,
      say_hi: form.say_hi,
      use_ai: form.use_ai,
      filter_inactive_hr: form.filter_inactive_hr,
      hr_active_days: form.hr_active_days,
      experience: form.experience,
      degree: form.degree,
      enable_company_check: form.enable_company_check,
    }

    try {
      if (editingId) {
        await schedulesApi.update(editingId, {
          name: form.name,
          config,
          run_time: form.run_time,
          days_of_week: form.days.join(','),
          enabled: form.enabled,
        })
      } else {
        await schedulesApi.create({
          name: form.name || `${getPlatformLabel(form.platform)}定时投递`,
          platform: form.platform,
          config,
          run_time: form.run_time,
          days_of_week: form.days.join(','),
          enabled: form.enabled,
        })
      }
      setShowModal(false)
      resetForm()
      loadSchedules()
    } catch (e) {
      alert('保存失败')
      console.error(e)
    }
  }

  const handleToggle = async (id: number, enabled: boolean) => {
    try {
      await schedulesApi.toggle(id, enabled)
      loadSchedules()
    } catch (e) {
      console.error('切换状态失败', e)
    }
  }

  const handleDelete = async (id: number) => {
    if (!confirm('确定删除这个定时任务吗？')) return
    try {
      await schedulesApi.remove(id)
      loadSchedules()
    } catch (e) {
      console.error('删除失败', e)
    }
  }

  const handleRunNow = async (id: number) => {
    try {
      await schedulesApi.runNow(id)
      alert('已触发立即执行')
    } catch (e) {
      alert('执行失败')
      console.error(e)
    }
  }

  const toggleDay = (day: string) => {
    setForm(prev => ({
      ...prev,
      days: prev.days.includes(day)
        ? prev.days.filter(d => d !== day)
        : [...prev.days, day].sort(),
    }))
  }

  const formatDays = (daysStr: string) => {
    const days = daysStr.split(',').filter(Boolean)
    if (days.length === 7) return '每天'
    if (days.length === 5 && ['0', '1', '2', '3', '4'].every(d => days.includes(d))) return '工作日'
    if (days.length === 2 && ['5', '6'].every(d => days.includes(d))) return '周末'
    return days.map(d => WEEKDAYS.find(w => w.value === d)?.label || d).join('、')
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-800">定时任务</h2>
          <p className="text-sm text-slate-500 mt-1">设置每天固定时间自动投递，无人值守运行</p>
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-md text-sm font-medium hover:bg-primary-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          新建定时任务
        </button>
      </div>

      {/* 任务列表 */}
      <div className="space-y-3">
        {loading ? (
          <div className="text-center py-12 text-slate-400">加载中...</div>
        ) : schedules.length === 0 ? (
          <div className="text-center py-16 bg-white rounded-lg border border-slate-200">
            <Clock className="w-12 h-12 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500">暂无定时任务</p>
            <p className="text-xs text-slate-400 mt-1">点击上方按钮创建第一个定时任务</p>
          </div>
        ) : (
          schedules.map(sched => (
            <div key={sched.id} className="bg-white rounded-lg border border-slate-200 p-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3">
                    <h3 className="font-medium text-slate-800">{sched.name}</h3>
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      sched.platform === 'boss' ? 'bg-green-100 text-green-700' :
                      sched.platform === 'job51' ? 'bg-blue-100 text-blue-700' :
                      sched.platform === 'zhilian' ? 'bg-orange-100 text-orange-700' :
                      'bg-purple-100 text-purple-700'
                    }`}>
                      {getPlatformLabel(sched.platform)}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      sched.enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'
                    }`}>
                      {sched.enabled ? '已启用' : '已禁用'}
                    </span>
                  </div>
                  <div className="mt-2 flex items-center gap-4 text-sm text-slate-500">
                    <span className="flex items-center gap-1">
                      <Clock className="w-3.5 h-3.5" />
                      {sched.run_time}
                    </span>
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5" />
                      {formatDays(sched.days_of_week)}
                    </span>
                    <span>关键词: {sched.config.keyword || '-'}</span>
                    <span>城市: {sched.config.city || '-'}</span>
                  </div>
                  <div className="mt-1 text-xs text-slate-400">
                    {sched.next_run_at && `下次执行: ${new Date(sched.next_run_at).toLocaleString('zh-CN')}`}
                    {sched.last_run_at && ` | 上次执行: ${new Date(sched.last_run_at).toLocaleString('zh-CN')}`}
                    {sched.last_run_status && ` (${sched.last_run_status})`}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleRunNow(sched.id)}
                    className="p-2 text-slate-500 hover:text-primary-600 hover:bg-primary-50 rounded transition-colors"
                    title="立即执行"
                  >
                    <Play className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleToggle(sched.id, !sched.enabled)}
                    className={`p-2 rounded transition-colors ${
                      sched.enabled
                        ? 'text-amber-600 hover:bg-amber-50'
                        : 'text-emerald-600 hover:bg-emerald-50'
                    }`}
                    title={sched.enabled ? '禁用' : '启用'}
                  >
                    {sched.enabled ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                  </button>
                  <button
                    onClick={() => openEdit(sched)}
                    className="p-2 text-slate-500 hover:text-primary-600 hover:bg-primary-50 rounded transition-colors"
                    title="编辑"
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(sched.id)}
                    className="p-2 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                    title="删除"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

      {/* 创建/编辑弹窗 */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-4 border-b border-slate-200">
              <h3 className="font-semibold text-slate-800">
                {editingId ? '编辑定时任务' : '新建定时任务'}
              </h3>
              <button onClick={() => setShowModal(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 space-y-4">
              {/* 基本信息 */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">任务名称</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={e => setForm({ ...form, name: e.target.value })}
                  placeholder="如：工作日早9点Boss投递"
                  className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">平台</label>
                  <select
                    value={form.platform}
                    onChange={e => setForm({ ...form, platform: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  >
                    {PLATFORMS.map(p => (
                      <option key={p.value} value={p.value}>{p.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">执行时间</label>
                  <input
                    type="time"
                    value={form.run_time}
                    onChange={e => setForm({ ...form, run_time: e.target.value })}
                    className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                </div>
              </div>

              {/* 星期选择 */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">执行日期</label>
                <div className="flex gap-2">
                  {WEEKDAYS.map(day => (
                    <button
                      key={day.value}
                      onClick={() => toggleDay(day.value)}
                      className={`w-9 h-9 rounded-md text-sm font-medium transition-colors ${
                        form.days.includes(day.value)
                          ? 'bg-primary-600 text-white'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                    >
                      {day.label}
                    </button>
                  ))}
                </div>
                <div className="mt-2 flex gap-2">
                  <button
                    onClick={() => setForm({ ...form, days: ['0', '1', '2', '3', '4'] })}
                    className="text-xs text-primary-600 hover:underline"
                  >
                    工作日
                  </button>
                  <button
                    onClick={() => setForm({ ...form, days: ['0', '1', '2', '3', '4', '5', '6'] })}
                    className="text-xs text-primary-600 hover:underline"
                  >
                    每天
                  </button>
                  <button
                    onClick={() => setForm({ ...form, days: ['5', '6'] })}
                    className="text-xs text-primary-600 hover:underline"
                  >
                    周末
                  </button>
                </div>
              </div>

              {/* 投递配置 */}
              <div className="pt-3 border-t border-slate-100">
                <p className="text-sm font-medium text-slate-700 mb-3">投递配置</p>
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">关键词</label>
                      <input
                        type="text"
                        value={form.keyword}
                        onChange={e => setForm({ ...form, keyword: e.target.value })}
                        className="w-full px-3 py-1.5 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">城市</label>
                      <input
                        type="text"
                        value={form.city}
                        onChange={e => setForm({ ...form, city: e.target.value })}
                        className="w-full px-3 py-1.5 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">薪资范围</label>
                      <input
                        type="text"
                        value={form.salary}
                        onChange={e => setForm({ ...form, salary: e.target.value })}
                        placeholder="如 10-20K"
                        className="w-full px-3 py-1.5 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">最大页数</label>
                      <input
                        type="number"
                        value={form.max_pages}
                        onChange={e => setForm({ ...form, max_pages: Number(e.target.value) })}
                        min={1}
                        max={50}
                        className="w-full px-3 py-1.5 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs text-slate-500 mb-1">打招呼语</label>
                    <textarea
                      value={form.say_hi}
                      onChange={e => setForm({ ...form, say_hi: e.target.value })}
                      rows={2}
                      className="w-full px-3 py-1.5 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                  </div>
                  <div className="flex items-center gap-4">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={form.use_ai}
                        onChange={e => setForm({ ...form, use_ai: e.target.checked })}
                        className="rounded"
                      />
                      <span className="text-sm text-slate-600">AI智能打招呼</span>
                    </label>
                    {form.platform === 'boss' && (
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={form.filter_inactive_hr}
                          onChange={e => setForm({ ...form, filter_inactive_hr: e.target.checked })}
                          className="rounded"
                        />
                        <span className="text-sm text-slate-600">过滤不活跃HR</span>
                      </label>
                    )}
                  </div>

                  {/* Boss高级过滤 */}
                  {form.platform === 'boss' && (
                    <div className="grid grid-cols-2 gap-2 pt-2">
                      <div>
                        <label className="block text-xs text-slate-500 mb-1">工作经验</label>
                        <select
                          value={form.experience}
                          onChange={e => setForm({ ...form, experience: e.target.value })}
                          className="w-full px-3 py-1.5 text-sm border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
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
                        <label className="block text-xs text-slate-500 mb-1">学历要求</label>
                        <select
                          value={form.degree}
                          onChange={e => setForm({ ...form, degree: e.target.value })}
                          className="w-full px-3 py-1.5 text-sm border border-slate-200 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
                        >
                          <option value="">不限</option>
                          <option value="204">大专</option>
                          <option value="205">本科</option>
                          <option value="206">硕士</option>
                          <option value="207">博士</option>
                        </select>
                      </div>
                    </div>
                  )}

                  {/* 公司背调开关 */}
                  <div className="flex items-center gap-2 pt-2">
                    <input
                      type="checkbox"
                      checked={form.enable_company_check}
                      onChange={e => setForm({ ...form, enable_company_check: e.target.checked })}
                      className="rounded"
                    />
                    <span className="text-sm text-slate-600">启用公司背调（自动跳过风险公司）</span>
                  </div>
                </div>
              </div>

              {/* 启用开关 */}
              <div className="flex items-center justify-between pt-3 border-t border-slate-100">
                <span className="text-sm text-slate-700">创建后立即启用</span>
                <button
                  onClick={() => setForm({ ...form, enabled: !form.enabled })}
                  className={`relative w-11 h-6 rounded-full transition-colors ${
                    form.enabled ? 'bg-primary-600' : 'bg-slate-300'
                  }`}
                >
                  <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                    form.enabled ? 'translate-x-5' : ''
                  }`} />
                </button>
              </div>
            </div>
            <div className="flex justify-end gap-2 p-4 border-t border-slate-200">
              <button
                onClick={() => setShowModal(false)}
                className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-md transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleSubmit}
                className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-md text-sm font-medium hover:bg-primary-700 transition-colors"
              >
                <Check className="w-4 h-4" />
                保存
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
