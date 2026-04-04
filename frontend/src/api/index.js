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
      const response = await fetch(`${BASE_URL}/chat/ask/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
