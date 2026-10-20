import { useState, useEffect } from 'react'
import { blacklistApi } from '../api/client'
import { Plus, Trash2, Ban } from 'lucide-react'

export default function Blacklist() {
  const [items, setItems] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [newItem, setNewItem] = useState({ company_name: '', platform: '', reason: '' })

  useEffect(() => {
    loadList()
  }, [])

  const loadList = async () => {
    setLoading(true)
    try {
      const response = await blacklistApi.list({ limit: 200 })
      setItems(response.data.items)
      setTotal(response.data.total)
    } catch (error) {
      console.error('加载黑名单失败', error)
    } finally {
      setLoading(false)
    }
  }

  const handleAdd = async () => {
    if (!newItem.company_name.trim()) {
      alert('请输入公司名称')
      return
    }
    try {
      await blacklistApi.add(newItem)
      setNewItem({ company_name: '', platform: '', reason: '' })
      setShowAdd(false)
      loadList()
    } catch (error: any) {
      alert(error.response?.data?.detail || '添加失败')
    }
  }

  const handleRemove = async (id: number) => {
    if (!confirm('确定要从黑名单移除吗？')) return
    try {
      await blacklistApi.remove(id)
      loadList()
    } catch (error) {
      alert('删除失败')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-fg">企业黑名单</h2>
          <p className="text-sm text-fg-mute mt-1">管理不想投递的公司，共 {total} 家</p>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="px-3 py-2 bg-primary-600 text-white rounded-md text-sm font-medium flex items-center gap-1.5 hover:bg-primary-700"
        >
          <Plus className="w-4 h-4" /> 添加
        </button>
      </div>

      {/* 添加表单 */}
      {showAdd && (
        <div className="bg-card rounded-lg border border-line p-4">
          <div className="grid grid-cols-1 min-[900px]:grid-cols-3 gap-4">
            <div>
              <label className="block text-xs font-medium text-fg-dim mb-1">公司名称 *</label>
              <input
                type="text"
                value={newItem.company_name}
                onChange={e => setNewItem({ ...newItem, company_name: e.target.value })}
                className="w-full px-3 py-2 border border-line rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="输入公司全称"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-fg-dim mb-1">平台</label>
              <select
                value={newItem.platform}
                onChange={e => setNewItem({ ...newItem, platform: e.target.value })}
                className="w-full px-3 py-2 border border-line rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="">全部平台</option>
                <option value="boss">Boss直聘</option>
                <option value="job51">51job</option>
                <option value="zhilian">智联招聘</option>
                <option value="liepin">猎聘</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-fg-dim mb-1">原因</label>
              <input
                type="text"
                value={newItem.reason}
                onChange={e => setNewItem({ ...newItem, reason: e.target.value })}
                className="w-full px-3 py-2 border border-line rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                placeholder="如：不匹配、已拒绝等"
              />
            </div>
          </div>
          <div className="mt-4 flex gap-2 justify-end">
            <button
              onClick={() => setShowAdd(false)}
              className="px-4 py-2 text-sm border border-line rounded-md hover:bg-surface text-fg-dim"
            >
              取消
            </button>
            <button
              onClick={handleAdd}
              className="px-4 py-2 text-sm bg-primary-600 text-white rounded-md hover:bg-primary-700"
            >
              确认添加
            </button>
          </div>
        </div>
      )}

      {/* 黑名单列表 */}
      <div className="bg-card rounded-lg border border-line overflow-x-auto">
        {loading ? (
          <div className="text-center py-12 text-fg-mute">加载中...</div>
        ) : items.length === 0 ? (
          <div className="text-center py-16">
            <Ban className="w-12 h-12 text-fg-mute mx-auto mb-3" />
            <p className="text-fg-mute">黑名单为空</p>
            <p className="text-xs text-fg-mute mt-1">添加公司后，投递时将自动跳过</p>
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-surface border-b border-line">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-fg-mute uppercase">公司名称</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-fg-mute uppercase">平台</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-fg-mute uppercase">原因</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-fg-mute uppercase">来源</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-fg-mute uppercase">添加时间</th>
                <th className="px-4 py-3 text-center text-xs font-medium text-fg-mute uppercase">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line-subtle">
              {items.map((item: any) => (
                <tr key={item.id} className="hover:bg-surface/40">
                  <td className="px-4 py-3 text-sm text-fg font-medium">{item.company_name}</td>
                  <td className="px-4 py-3 text-sm text-fg-dim">
                    {item.platform === 'boss' ? 'Boss直聘' : item.platform === 'job51' ? '51job' : item.platform === 'zhilian' ? '智联招聘' : item.platform === 'liepin' ? '猎聘' : '全部'}
                  </td>
                  <td className="px-4 py-3 text-sm text-fg-dim">{item.reason || '-'}</td>
                  <td className="px-4 py-3 text-sm">
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      item.source === 'auto' ? 'bg-primary/10 text-primary-300' : 'bg-surface text-fg-mute'
                    }`}>
                      {item.source === 'auto' ? '自动' : '手动'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-fg-mute">
                    {new Date(item.created_at).toLocaleString('zh-CN')}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button
                      onClick={() => handleRemove(item.id)}
                      className="text-red-500 hover:text-red-700 p-1"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
