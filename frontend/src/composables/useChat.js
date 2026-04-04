import { ref } from 'vue'
import { api } from '../api/index.js'

const sessions = ref([])
const currentSession = ref(null)
const messages = ref([])
const loading = ref({ sessions: false, messages: false, send: false })
const streamingContent = ref('')
const thinkingStatus = ref('')

export function useChat() {
  async function fetchSessions() {
    loading.value.sessions = true
    const result = await api.chat.listSessions()
    loading.value.sessions = false
    if (result.ok) {
      sessions.value = result.data
    }
    return result
  }

  async function createSession(title) {
    const result = await api.chat.createSession(title)
    if (result.ok) {
      sessions.value.unshift(result.data)
      currentSession.value = result.data
      messages.value = []
    }
    return result
  }

  async function selectSession(session) {
    currentSession.value = session
    await fetchMessages(session.id)
  }

  async function fetchMessages(sessionId) {
    loading.value.messages = true
    const result = await api.chat.getMessages(sessionId)
    loading.value.messages = false
    if (result.ok) {
      messages.value = result.data
    }
    return result
  }

  async function deleteSession(sessionId) {
    const result = await api.chat.deleteSession(sessionId)
    if (result.ok) {
      sessions.value = sessions.value.filter(s => s.id !== sessionId)
      if (currentSession.value?.id === sessionId) {
        currentSession.value = null
        messages.value = []
      }
    }
    return result
  }

  async function* sendMessage(sessionId, message) {
    yield* api.chat.askStream(sessionId, message)
  }

  return {
    sessions,
    currentSession,
    messages,
    loading,
    streamingContent,
    thinkingStatus,
    fetchSessions,
    createSession,
    selectSession,
    fetchMessages,
    deleteSession,
    sendMessage,
  }
}
