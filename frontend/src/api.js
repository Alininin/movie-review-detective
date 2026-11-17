// 统一的接口调用封装：所有请求都走真实后端，前端不保存任何预置结果
const BASE = ''

async function request(path, options = {}) {
  const response = await fetch(BASE + path, options)
  const contentType = response.headers.get('content-type') || ''
  const isJson = contentType.includes('application/json')
  const body = isJson ? await response.json() : await response.text()

  if (!response.ok) {
    let message = `请求失败（HTTP ${response.status}）`
    if (isJson && body && body.detail) {
      message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } else if (typeof body === 'string' && body.trim()) {
      message = body.slice(0, 200)
    }
    const error = new Error(message)
    error.status = response.status
    throw error
  }
  return body
}

function postJSON(path, payload) {
  return request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export const api = {
  health: () => request('/api/health'),

  datasetStats: () => request('/api/dataset/stats'),
  reviews: (params) => {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') query.append(key, value)
    })
    return request(`/api/reviews?${query.toString()}`)
  },

  predict: (text) => postJSON('/api/predict', { text }),
  batch: (file) => {
    const form = new FormData()
    form.append('file', file)
    return request('/api/batch', { method: 'POST', body: form })
  },

  search: (query, topK = 5) => postJSON('/api/search', { query, top_k: topK }),
  presetQueries: () => request('/api/search/queries'),

  challengePresets: () => request('/api/challenge/presets'),
  challenge: (original, rewritten) => postJSON('/api/challenge', { original, rewritten }),

  experiments: () => request('/api/experiments'),
  history: (limit = 20, offset = 0) => request(`/api/history?limit=${limit}&offset=${offset}`),
  deleteHistory: (id) => request(`/api/history/${id}`, { method: 'DELETE' }),
}

// 分类分数只保留 4 位，明确说明它不是概率
export function formatScore(value) {
  if (value === null || value === undefined) return '—'
  return Number(value).toFixed(4)
}

export function formatMs(value) {
  if (value === null || value === undefined) return '—'
  return `${Number(value).toFixed(1)} ms`
}
