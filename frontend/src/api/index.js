import { log, warn, error as logError } from '../utils/logger.js'

const BASE_URL = '/api/v1'

function clearAuthState() {
  localStorage.removeItem('user')
  localStorage.removeItem('user_role')
}

function normalizeNetworkError(error) {
  const detail = error instanceof Error ? error.message : 'Network error'
  return { ok: false, status: 0, data: { detail } }
}

async function request(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  }

  log(`[API] ${options.method || 'GET'} ${path}`, options.body || '')

  let response
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      credentials: 'include',  // Include cookies for HttpOnly cookie auth
      headers,
      ...options,
    })
  } catch (error) {
    logError(`[API] Network error for ${path}:`, error)
    return normalizeNetworkError(error)
  }

  const data = await response.json().catch(() => ({}))
  log(`[API] Response for ${path}:`, { status: response.status, ok: response.ok, data })

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
    const retryable = result.status === 0 || result.status >= 500 || result.status === 429

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
    register: (email, password) => requestWithRetry('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }, { retries: 1 }),
    login: (email, password) => requestWithRetry('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }, { retries: 1 }),
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
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(`${BASE_URL}/documents/upload`, {
        method: 'POST',
        credentials: 'include',  // Include cookies for HttpOnly cookie auth
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
      const headers = { 'Content-Type': 'application/json' }

      const response = await fetch(`${BASE_URL}/chat/ask/stream`, {
        method: 'POST',
        credentials: 'include',  // Include cookies for HttpOnly cookie auth
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
            } catch {
              warn('Parse error:', data)
            }
          }
        }
      }
    },
    // Guest chat - no authentication required
    guestMessage: async function* (sessionId, message) {
      const headers = { 'Content-Type': 'application/json' }
      const body = { message }
      if (sessionId) {
        body.session_id = sessionId
      }

      const response = await fetch(`${BASE_URL}/chat/guest/message`, {
        method: 'POST',
        credentials: 'include',  // Include cookies for session tracking
        headers,
        body: JSON.stringify(body),
      })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      // Get session ID from response header for subsequent requests
      const newSessionId = response.headers.get('X-Session-Id')

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
              const parsed = JSON.parse(data)
              parsed.session_id = newSessionId
              yield parsed
            } catch {
              warn('Parse error:', data)
            }
          }
        }
      }
    },
  },

  // Exhibits (public API)
  exhibits: {
    list: (params = {}) => {
      // Filter out null/undefined values to avoid malformed queries
      const filteredParams = Object.fromEntries(
        Object.entries(params).filter(([, v]) => v != null)
      )
      return request(`/exhibits?${new URLSearchParams(filteredParams)}`)
    },
    get: (id) => request(`/exhibits/${id}`),
  },

  // Admin
  admin: {
    // Exhibits
    listExhibits: (params = {}) => request(`/admin/exhibits?${new URLSearchParams(params)}`),
    createExhibit: (data) => request('/admin/exhibits', {
      method: 'POST',
      body: JSON.stringify(data)
    }),
    updateExhibit: (id, data) => request(`/admin/exhibits/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data)
    }),
    deleteExhibit: (id) => request(`/admin/exhibits/${id}`, { method: 'DELETE' }),

    // Tour Paths
    listTourPaths: () => request('/admin/tour-paths'),
    createTourPath: (data) => request('/admin/tour-paths', {
      method: 'POST',
      body: JSON.stringify(data)
    }),
    updateTourPath: (id, data) => request(`/admin/tour-paths/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data)
    }),
    deleteTourPath: (id) => request(`/admin/tour-paths/${id}`, { method: 'DELETE' }),

    // Prompts
    prompts: {
      list: (params = {}) => {
        const filteredParams = Object.fromEntries(
          Object.entries(params).filter(([, v]) => v != null)
        )
        return request(`/admin/prompts?${new URLSearchParams(filteredParams)}`)
      },
      get: (key) => request(`/admin/prompts/${key}`),
      update: (key, data) => request(`/admin/prompts/${key}`, {
        method: 'PUT',
        body: JSON.stringify(data)
      }),
      listVersions: (key, params = {}) => {
        const filteredParams = Object.fromEntries(
          Object.entries(params).filter(([, v]) => v != null)
        )
        return request(`/admin/prompts/${key}/versions?${new URLSearchParams(filteredParams)}`)
      },
      getVersion: (key, version) => request(`/admin/prompts/${key}/versions/${version}`),
      rollback: (key, version) => request(`/admin/prompts/${key}/versions/${version}/rollback`, {
        method: 'POST'
      }),
      reload: (key) => request(`/admin/prompts/${key}/reload`, { method: 'POST' }),
      reloadAll: () => request('/admin/prompts/reload-all', { method: 'POST' }),
    },
  },

  // Curator (AI-powered tour planning)
  curator: {
    planTour: (availableTime, interests) => request('/curator/plan-tour', {
      method: 'POST',
      body: JSON.stringify({ available_time: availableTime, interests })
    }),
    generateNarrative: (exhibitId) => request('/curator/narrative', {
      method: 'POST',
      body: JSON.stringify({ exhibit_id: exhibitId })
    }),
    getReflectionPrompts: (exhibitId) => request('/curator/reflection', {
      method: 'POST',
      body: JSON.stringify({ exhibit_id: exhibitId })
    }),
  },

  // User profile preferences
  profile: {
    get: () => request('/profile'),
    update: (data) => request('/profile', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),
  },
}
