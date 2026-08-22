import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 任务运行相关API
export const runsApi = {
  start: (params: {
    platform: string
    keyword: string
    city?: string
    salary?: string
    max_pages?: number
    say_hi?: string
    use_ai?: boolean
    filter_inactive_hr?: boolean
    hr_active_days?: number
    experience?: string
    degree?: string
    enable_company_check?: boolean
  }) => api.post('/runs/start', null, { params }),

  stop: (runId: number) => api.post(`/runs/${runId}/stop`),

  get: (runId: number) => api.get(`/runs/${runId}`),

  list: (params?: { platform?: string; limit?: number; offset?: number }) =>
    api.get('/runs', { params }),

  getPlatforms: () => api.get('/runs/platforms'),
}

// 配置相关API
export const configApi = {
  getAI: () => api.get('/config/ai'),
  updateAI: (data: any) => api.put('/config/ai', data),
  getNotify: () => api.get('/config/notify'),
  updateNotify: (data: any) => api.put('/config/notify', data),
  testNotify: () => api.post('/config/notify/test'),
  getPlatform: (platform: string) => api.get(`/config/platform/${platform}`),
  updatePlatform: (platform: string, key: string, value: any) =>
    api.put(`/config/platform/${platform}/${key}`, value),
}

// 结果与统计API
export const resultsApi = {
  list: (params?: { run_id?: number; platform?: string; status?: string; limit?: number; offset?: number }) =>
    api.get('/results', { params }),
  stats: (params?: { platform?: string; days?: number }) =>
    api.get('/results/stats', { params }),
  trend: (params?: { platform?: string; days?: number }) =>
    api.get('/results/trend', { params }),
}

// 黑名单API
export const blacklistApi = {
  list: (params?: { platform?: string; limit?: number; offset?: number }) =>
    api.get('/blacklist', { params }),
  add: (data: { company_name: string; platform?: string; reason?: string }) =>
    api.post('/blacklist', data),
  remove: (id: number) => api.delete(`/blacklist/${id}`),
}

// 定时任务API
export const schedulesApi = {
  list: (params?: { platform?: string }) =>
    api.get('/schedules', { params }),
  get: (id: number) => api.get(`/schedules/${id}`),
  create: (data: {
    name?: string
    platform: string
    config?: Record<string, any>
    run_time?: string
    days_of_week?: string
    enabled?: boolean
  }) => api.post('/schedules', data),
  update: (id: number, data: Record<string, any>) =>
    api.put(`/schedules/${id}`, data),
  remove: (id: number) => api.delete(`/schedules/${id}`),
  toggle: (id: number, enabled: boolean) =>
    api.post(`/schedules/${id}/toggle`, null, { params: { enabled } }),
  runNow: (id: number) => api.post(`/schedules/${id}/run`),
}

// 健康检查
export const healthApi = {
  check: () => api.get('/health'),
}

// 公司背调API
export const companyCheckApi = {
  check: (params: { company: string; job_title?: string }) =>
    api.get('/company-check/check', { params }),
  listKeywords: () => api.get('/company-check/keywords'),
  addKeyword: (data: { keyword: string; level: string }) =>
    api.post('/company-check/keywords', data),
  removeKeyword: (keyword: string) =>
    api.delete(`/company-check/keywords/${encodeURIComponent(keyword)}`),
}

// SSE事件订阅
export function subscribeRunEvents(runId: number, onMessage: (data: any) => void, onError?: () => void) {
  const eventSource = new EventSource(`/api/runs/${runId}/events`)

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      onMessage(data)
    } catch (e) {
      console.error('解析SSE消息失败', e)
    }
  }

  eventSource.onerror = () => {
    console.warn('SSE连接断开')
    onError?.()
  }

  return () => eventSource.close()
}

// 批量投递任务API
export const batchApi = {
  start: (params: {
    keyword: string
    city?: string
    max_pages?: number
    say_hi?: string
    enable_company_check?: boolean
    platforms?: string
    max_retries?: number
  }) => api.post('/batch/start', null, { params }),

  get: (batchId: number) => api.get(`/batch/${batchId}`),

  list: (params?: { limit?: number }) => api.get('/batch', { params }),

  results: (batchId: number) => api.get(`/batch/${batchId}/results`),

  pausePlatform: (batchId: number, platform: string) =>
    api.post(`/batch/${batchId}/platform/${platform}/pause`),

  resumePlatform: (batchId: number, platform: string) =>
    api.post(`/batch/${batchId}/platform/${platform}/resume`),

  stopPlatform: (batchId: number, platform: string) =>
    api.post(`/batch/${batchId}/platform/${platform}/stop`),

  stop: (batchId: number) => api.post(`/batch/${batchId}/stop`),
}

// 批量任务SSE事件订阅
export function subscribeBatchEvents(batchId: number, onMessage: (data: any) => void, onError?: () => void) {
  const eventSource = new EventSource(`/api/batch/${batchId}/events`)

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      onMessage(data)
    } catch (e) {
      console.error('解析批量SSE消息失败', e)
    }
  }

  eventSource.onerror = () => {
    console.warn('批量SSE连接断开')
    onError?.()
  }

  return () => eventSource.close()
}

export default api
