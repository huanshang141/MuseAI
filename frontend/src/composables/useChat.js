import { ref } from 'vue'
import { api } from '../api/index.js'
import { useAuth } from './useAuth.js'

const sessions = ref([])
const currentSession = ref(null)
const messages = ref([])
const loading = ref({ sessions: false, messages: false, send: false })
const streamingContent = ref('')
const thinkingStatus = ref('')
const error = ref(null)

export function useChat() {
  const { isAuthenticated } = useAuth()

  function handleError(result) {
    if (result.status === 401) {
      error.value = '请先登录'
    } else {
      error.value = result.data?.detail || '请求失败'
    }
    return result
  }

  async function fetchSessions() {
    if (!isAuthenticated.value) {
      error.value = '请先登录'
      return { ok: false, status: 401, data: { detail: '未认证' } }
    }

    loading.value.sessions = true
    error.value = null
    const result = await api.chat.listSessions()
    loading.value.sessions = false

    if (!result.ok) {
      return handleError(result)
    }

    sessions.value = result.data
    return result
  }

  async function createSession(title) {
    if (!isAuthenticated.value) {
      error.value = '请先登录'
      return { ok: false, status: 401, data: { detail: '未认证' } }
    }

    const result = await api.chat.createSession(title)
    if (!result.ok) {
      return handleError(result)
    }

    sessions.value.unshift(result.data)
    currentSession.value = result.data
    messages.value = []
    return result
  }

  async function selectSession(session) {
    currentSession.value = session
    await fetchMessages(session.id)
  }

  async function fetchMessages(sessionId) {
    if (!isAuthenticated.value) {
      error.value = '请先登录'
      return { ok: false, status: 401, data: { detail: '未认证' } }
    }

    loading.value.messages = true
    error.value = null
    const result = await api.chat.getMessages(sessionId)
    loading.value.messages = false

    if (!result.ok) {
      return handleError(result)
    }

    messages.value = result.data
    return result
  }

  async function deleteSession(sessionId) {
    if (!isAuthenticated.value) {
      error.value = '请先登录'
      return { ok: false, status: 401, data: { detail: '未认证' } }
    }

    const result = await api.chat.deleteSession(sessionId)
    if (!result.ok) {
      return handleError(result)
    }

    sessions.value = sessions.value.filter(s => s.id !== sessionId)
    if (currentSession.value?.id === sessionId) {
      currentSession.value = null
      messages.value = []
    }
    return result
  }

  async function* sendMessage(sessionId, message) {
    if (!isAuthenticated.value) {
      throw new Error('请先登录')
    }
    yield* api.chat.askStream(sessionId, message)
  }

  return {
    sessions,
    currentSession,
    messages,
    loading,
    streamingContent,
    thinkingStatus,
    error,
    fetchSessions,
    createSession,
    selectSession,
    fetchMessages,
    deleteSession,
    sendMessage,
  }
}
