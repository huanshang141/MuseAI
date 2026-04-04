const BASE_URL = '/api/v1'

async function request(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })
  
  const data = await response.json().catch(() => ({}))
  return {
    ok: response.ok,
    status: response.status,
    data,
  }
}

export const api = {
  health: () => request('/health'),
  ready: () => request('/ready'),
  
  documents: {
    list: () => request('/documents'),
    get: (id) => request(`/documents/${id}`),
    status: (id) => request(`/documents/${id}/status`),
    delete: (id) => request(`/documents/${id}`, { method: 'DELETE' }),
    upload: async (file) => {
      const formData = new FormData()
      formData.append('file', file)
      const response = await fetch(`${BASE_URL}/documents/upload`, {
        method: 'POST',
        body: formData,
      })
      const data = await response.json().catch(() => ({}))
      return { ok: response.ok, status: response.status, data }
    },
  },
}
