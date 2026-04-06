const BASE_URL = '/api/v1'

function getToken() {
  return localStorage.getItem('access_token')
}

function clearAuthState() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('user')
  localStorage.removeItem('user_role')
}

function normalizeNetworkError(error) {
  const detail = error instanceof Error ? error.message : 'Network error'
  return { ok: false, status: 0, data: { detail } }
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

  console.log(`[API] ${options.method || 'GET'} ${path}`, options.body || '')

  let response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers,
      ...options,
    })
  } catch (error) {
    console.error(`[API] Network error for ${path}:`, error)
    return normalizeNetworkError(error)
  }

  const data = await response.json().catch(() => ({}))
  console.log(`[API] Response for ${path}:`, { status: response.status, ok: response.ok, data })

  if (response.status === 401) {
    clearAuthState()
  }

  return {
    ok: response.ok,
    status: response.status,
    data,
  }
}

function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function requestWithRetry(path, options = {}, config = { retries: 0, baseDelayMs: 150 }) {
  let attempt = 0
  while (true) {
    const result = await request(path, options)
    const retryable = result.status === 0 || result.status >= 500

    if (!retryable || attempt >= config.retries) {
      return result
    }

    attempt += 1
    await wait(config.baseDelayMs * attempt)
  }
}

export const api = {
  // Health endpoints (public) - idempotent, safe to retry
  health: () => requestWithRetry('/health', {}, { retries: 1, baseDelayMs: 150 }),
  ready: () => requestWithRetry('/ready', {}, { retries: 1, baseDelayMs: 150 }),

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
