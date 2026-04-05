const BASE_URL = '/api/v1'

function getToken() {
  return localStorage.getItem('access_token')
}

async function request(path, options = {}) {
  const token = getToken()
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  // Add Authorization header if token exists
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    headers,
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
  // Health endpoints (public)
  health: () => request('/health'),
  ready: () => request('/ready'),

  // Auth endpoints
  auth: {
    register: (email, password) => request('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
    login: (email, password) => request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
    logout: () => request('/auth/logout', {
      method: 'POST',
    }),
  },

  documents: {
    list: () => request('/documents'),
    get: (id) => request(`/documents/${id}`),
    status: (id) => request(`/documents/${id}/status`),
    delete: (id) => request(`/documents/${id}`, { method: 'DELETE' }),
    upload: async (file) => {
      const token = getToken()
      const formData = new FormData()
      formData.append('file', file)

      const headers = {}
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }

      const response = await fetch(`${BASE_URL}/documents/upload`, {
        method: 'POST',
        headers,
        body: formData,
      })
      const data = await response.json().catch(() => ({}))
      return { ok: response.ok, status: response.status, data }
    },
  },

  chat: {
    createSession: (title) => request('/chat/sessions', {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),
    listSessions: () => request('/chat/sessions'),
    getSession: (id) => request(`/chat/sessions/${id}`),
    deleteSession: (id) => request(`/chat/sessions/${id}`, { method: 'DELETE' }),
    getMessages: (sessionId) => request(`/chat/sessions/${sessionId}/messages`),
    ask: (sessionId, message) => request('/chat/ask', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, message }),
    }),
    askStream: async function* (sessionId, message) {
      const token = getToken()
      const headers = { 'Content-Type': 'application/json' }
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }

      const response = await fetch(`${BASE_URL}/chat/ask/stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ session_id: sessionId, message }),
      })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (data === '[DONE]') return
            try {
              yield JSON.parse(data)
            } catch (e) {
              console.warn('Parse error:', data)
            }
          }
        }
      }
    },
  },
}
