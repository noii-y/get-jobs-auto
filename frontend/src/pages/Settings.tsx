import { useState, useEffect } from 'react'
import { configApi, companyCheckApi } from '../api/client'
import { Bot, Bell, Save, CheckCircle, Shield, Plus, Trash2 } from 'lucide-react'

export default function Settings() {
  const [aiConfig, setAiConfig] = useState({
    name: 'default',
    base_url: 'https://api.openai.com/v1',
    api_key: '',
    model: 'gpt-4o-mini',
    enabled: false,
    api_key_set: false,
  })

  const [notifyConfig, setNotifyConfig] = useState({
    webhook_url: '',
    enabled: false,
    notify_start: true,
    notify_finish: true,
    notify_error: true,
  })

  const [saved, setSaved] = useState('')
  const [loading, setLoading] = useState(true)

  // 公司背调风险关键词
  const [riskKeywords, setRiskKeywords] = useState<any[]>([])
  const [newKeyword, setNewKeyword] = useState('')
  const [newKeywordLevel, setNewKeywordLevel] = useState('medium')
  const [keywordsLoading, setKeywordsLoading] = useState(false)

  useEffect(() => {
    loadConfig()
  }, [])

  const loadConfig = async () => {
    try {
      const [aiRes, notifyRes, keywordsRes] = await Promise.all([
        configApi.getAI(),
        configApi.getNotify(),
        companyCheckApi.listKeywords(),
      ])
      setAiConfig({ ...aiRes.data, api_key: '' })
      setNotifyConfig(notifyRes.data)
      setRiskKeywords(keywordsRes.data.items)
    } catch (error) {
      console.error('加载配置失败', error)
    } finally {
      setLoading(false)
    }
  }

  const saveAI = async () => {
    try {
      await configApi.updateAI(aiConfig)
      setSaved('ai')
      setTimeout(() => setSaved(''), 2000)
      loadConfig()
    } catch (error) {
      alert('保存AI配置失败')
    }
  }

  const saveNotify = async () => {
    try {
      await configApi.updateNotify(notifyConfig)
      setSaved('notify')
      setTimeout(() => setSaved(''), 2000)
    } catch (error) {
      alert('保存通知配置失败')
    }
  }

  const testNotify = async () => {
    try {
      const res = await configApi.testNotify()
      alert(res.data.success ? '测试消息已发送！' : '发送失败，请检查Webhook地址')
    } catch (error) {
      alert('测试失败')
    }
  }

  const addKeyword = async () => {
    if (!newKeyword.trim()) return
    setKeywordsLoading(true)
    try {
      await companyCheckApi.addKeyword({ keyword: newKeyword.trim(), level: newKeywordLevel })
      setNewKeyword('')
      const res = await companyCheckApi.listKeywords()
      setRiskKeywords(res.data.items)
    } catch (error) {
      alert('添加失败')
    } finally {
      setKeywordsLoading(false)
    }
  }

  const removeKeyword = async (keyword: string) => {
    if (!confirm(`确定删除关键词"${keyword}"吗？`)) return
    try {
      await companyCheckApi.removeKeyword(keyword)
      const res = await companyCheckApi.listKeywords()
      setRiskKeywords(res.data.items)
    } catch (error) {
      alert('删除失败')
    }
  }

  if (loading) {
    return <div className="text-center py-12 text-slate-500">加载中...</div>
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h2 className="text-xl font-bold text-slate-800">设置</h2>
        <p className="text-sm text-slate-500 mt-1">配置AI服务和通知功能</p>
      </div>

      {/* AI配置 */}
      <div className="bg-white rounded-lg border border-slate-200 p-6">
        <div className="flex items-center gap-2 mb-5">
          <Bot className="w-5 h-5 text-primary-600" />
          <h3 className="text-base font-semibold text-slate-800">AI 智能打招呼配置</h3>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-700">启用AI打招呼</p>
              <p className="text-xs text-slate-400">根据职位描述生成个性化问候语</p>
            </div>
            <button
              onClick={() => setAiConfig({ ...aiConfig, enabled: !aiConfig.enabled })}
              className={`relative w-11 h-6 rounded-full transition-colors ${
                aiConfig.enabled ? 'bg-primary-600' : 'bg-slate-300'
              }`}
            >
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                aiConfig.enabled ? 'translate-x-5' : ''
              }`} />
            </button>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">API Base URL</label>
            <input
              type="text"
              value={aiConfig.base_url}
              onChange={e => setAiConfig({ ...aiConfig, base_url: e.target.value })}
              className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="https://api.openai.com/v1"
            />
            <p className="text-xs text-slate-400 mt-1">支持OpenAI兼容接口（如DeepSeek、通义千问等）</p>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">
              API Key {aiConfig.api_key_set && <span className="text-green-600">（已设置）</span>}
            </label>
            <input
              type="password"
              value={aiConfig.api_key}
              onChange={e => setAiConfig({ ...aiConfig, api_key: e.target.value })}
              className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder={aiConfig.api_key_set ? '留空则不修改' : '输入API Key'}
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">模型名称</label>
            <input
              type="text"
              value={aiConfig.model}
              onChange={e => setAiConfig({ ...aiConfig, model: e.target.value })}
              className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="gpt-4o-mini / deepseek-chat 等"
            />
          </div>

          <button
            onClick={saveAI}
            className="flex items-center gap-1.5 px-4 py-2 bg-primary-600 text-white rounded-md text-sm font-medium hover:bg-primary-700"
          >
            {saved === 'ai' ? <CheckCircle className="w-4 h-4" /> : <Save className="w-4 h-4" />}
            {saved === 'ai' ? '已保存' : '保存配置'}
          </button>
        </div>
      </div>

      {/* 通知配置 */}
      <div className="bg-white rounded-lg border border-slate-200 p-6">
        <div className="flex items-center gap-2 mb-5">
          <Bell className="w-5 h-5 text-primary-600" />
          <h3 className="text-base font-semibold text-slate-800">企业微信通知配置</h3>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-700">启用通知</p>
              <p className="text-xs text-slate-400">任务开始/完成/异常时推送消息</p>
            </div>
            <button
              onClick={() => setNotifyConfig({ ...notifyConfig, enabled: !notifyConfig.enabled })}
              className={`relative w-11 h-6 rounded-full transition-colors ${
                notifyConfig.enabled ? 'bg-primary-600' : 'bg-slate-300'
              }`}
            >
              <span className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform ${
                notifyConfig.enabled ? 'translate-x-5' : ''
              }`} />
            </button>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">Webhook URL</label>
            <input
              type="text"
              value={notifyConfig.webhook_url}
              onChange={e => setNotifyConfig({ ...notifyConfig, webhook_url: e.target.value })}
              className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx"
            />
          </div>

          <div className="space-y-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={notifyConfig.notify_start}
                onChange={e => setNotifyConfig({ ...notifyConfig, notify_start: e.target.checked })}
                className="w-4 h-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
              />
              <span className="text-sm text-slate-700">任务开始时通知</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={notifyConfig.notify_finish}
                onChange={e => setNotifyConfig({ ...notifyConfig, notify_finish: e.target.checked })}
                className="w-4 h-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
              />
              <span className="text-sm text-slate-700">任务完成时通知（含统计数据）</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={notifyConfig.notify_error}
                onChange={e => setNotifyConfig({ ...notifyConfig, notify_error: e.target.checked })}
                className="w-4 h-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
              />
              <span className="text-sm text-slate-700">任务异常时通知</span>
            </label>
          </div>

          <div className="flex gap-2">
            <button
              onClick={saveNotify}
              className="flex items-center gap-1.5 px-4 py-2 bg-primary-600 text-white rounded-md text-sm font-medium hover:bg-primary-700"
            >
              {saved === 'notify' ? <CheckCircle className="w-4 h-4" /> : <Save className="w-4 h-4" />}
              {saved === 'notify' ? '已保存' : '保存配置'}
            </button>
            <button
              onClick={testNotify}
              className="px-4 py-2 border border-slate-300 rounded-md text-sm text-slate-700 hover:bg-slate-50"
            >
              发送测试消息
            </button>
          </div>
        </div>
      </div>

      {/* 公司背调配置 */}
      <div className="bg-white rounded-lg border border-slate-200 p-6">
        <div className="flex items-center gap-2 mb-5">
          <Shield className="w-5 h-5 text-primary-600" />
          <h3 className="text-base font-semibold text-slate-800">公司背调风险关键词</h3>
        </div>

        <p className="text-sm text-slate-500 mb-4">
          投递前自动检测公司名称和职位描述中的风险关键词，高风险公司自动跳过。内置 {riskKeywords.filter(k => !k.custom).length} 个关键词，可自定义添加。
        </p>

        {/* 添加关键词 */}
        <div className="flex gap-2 mb-4">
          <input
            type="text"
            value={newKeyword}
            onChange={e => setNewKeyword(e.target.value)}
            placeholder="输入风险关键词，如：培训贷"
            className="flex-1 px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            onKeyDown={e => e.key === 'Enter' && addKeyword()}
          />
          <select
            value={newKeywordLevel}
            onChange={e => setNewKeywordLevel(e.target.value)}
            className="px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="high">高风险</option>
            <option value="medium">中风险</option>
            <option value="low">低风险</option>
          </select>
          <button
            onClick={addKeyword}
            disabled={keywordsLoading || !newKeyword.trim()}
            className="flex items-center gap-1.5 px-4 py-2 bg-primary-600 text-white rounded-md text-sm font-medium hover:bg-primary-700 disabled:opacity-50"
          >
            <Plus className="w-4 h-4" />
            添加
          </button>
        </div>

        {/* 关键词列表 */}
        <div className="border border-slate-200 rounded-md overflow-hidden">
          <div className="max-h-64 overflow-y-auto">
            {riskKeywords.length === 0 ? (
              <div className="p-4 text-center text-sm text-slate-400">暂无关键词</div>
            ) : (
              riskKeywords.map((kw: any) => (
                <div key={kw.keyword} className="flex items-center justify-between px-4 py-2 border-b border-slate-100 last:border-b-0 hover:bg-slate-50">
                  <div className="flex items-center gap-3">
                    <span className="text-sm text-slate-700">{kw.keyword}</span>
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      kw.level === 'high' ? 'bg-red-100 text-red-700' :
                      kw.level === 'medium' ? 'bg-amber-100 text-amber-700' :
                      'bg-yellow-100 text-yellow-700'
                    }`}>
                      {kw.level_label}
                    </span>
                    {kw.custom && (
                      <span className="text-xs text-slate-400">自定义</span>
                    )}
                  </div>
                  {kw.custom && (
                    <button
                      onClick={() => removeKeyword(kw.keyword)}
                      className="p-1 text-slate-400 hover:text-red-600 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
