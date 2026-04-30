import { ref } from 'vue'
import { api } from '../api/index.js'
import { useAuth } from './useAuth.js'
import { log, error as logError } from '../utils/logger.js'

const sessions = ref([])
const currentSession = ref(null)
const messages = ref([])
const loading = ref({ sessions: false, messages: false, send: false })
const streamingContent = ref('')
const thinkingStatus = ref('')
const ragSteps = ref([])
const error = ref(null)

// RAG步骤定义
const RAG_STEP_CONFIG = {
  rewrite: { label: '查询分析', icon: '🔍' },
  retrieve: { label: '文档检索', icon: '📚' },
  rerank: { label: '结果排序', icon: '📊' },
  evaluate: { label: '质量评估', icon: '✓' },
  transform: { label: '查询优化', icon: '🔄' },
  generate: { label: '生成回答', icon: '✨' },
}

// Guest session ID stored in memory (lost on page close)
let guestSessionId = null

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
      // Guest mode: keep local in-memory session visible in sidebar
      sessions.value = currentSession.value ? [currentSession.value] : []
      return { ok: true, status: 200, data: { sessions: sessions.value, total: sessions.value.length } }
    }

    loading.value.sessions = true
    error.value = null
    const result = await api.chat.listSessions()
    loading.value.sessions = false

    if (!result.ok) {
      return handleError(result)
    }

    sessions.value = result.data.sessions || result.data
    return result
  }

  async function createSession(title) {
    if (!isAuthenticated.value) {
      // Guest mode: create a temporary session ID
      const tempSession = {
        id: guestSessionId || crypto.randomUUID(),
        title: title || '新对话',
        created_at: new Date().toISOString(),
      }
      guestSessionId = tempSession.id
      currentSession.value = tempSession
      sessions.value = [tempSession]
      messages.value = []
      return { ok: true, status: 200, data: tempSession }
    }

    log('[useChat] Creating session with title:', title)
    const result = await api.chat.createSession(title)
    log('[useChat] Create session result:', result)

    if (!result.ok) {
      logError('[useChat] Create session failed:', result)
      return handleError(result)
    }

    log('[useChat] Setting currentSession to:', result.data)
    sessions.value.unshift(result.data)
    currentSession.value = result.data
    messages.value = []
    log('[useChat] currentSession is now:', currentSession.value)
    return result
  }

  async function selectSession(session) {
    currentSession.value = session
    if (isAuthenticated.value) {
      await fetchMessages(session.id)
    } else {
      // Guest mode: no message history
      sessions.value = [session]
      messages.value = []
    }
  }

  async function fetchMessages(sessionId) {
    if (!isAuthenticated.value) {
      // Guest mode: no message history
      messages.value = []
      return { ok: true, status: 200, data: { messages: [], total: 0 } }
    }

    loading.value.messages = true
    error.value = null
    const result = await api.chat.getMessages(sessionId)
    loading.value.messages = false

    if (!result.ok) {
      return handleError(result)
    }

    messages.value = result.data.messages || result.data
    return result
  }

  async function deleteSession(sessionId) {
    if (!isAuthenticated.value) {
      // Guest mode: just clear current session
      sessions.value = sessions.value.filter(s => s.id !== sessionId)
      if (currentSession.value?.id === sessionId) {
        currentSession.value = null
        messages.value = []
        guestSessionId = null
      }
      return { ok: true, status: 200, data: { status: 'deleted', session_id: sessionId } }
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

  async function* sendMessage(sessionId, message, ttsOptions = {}) {
    // 重置RAG步骤状态
    ragSteps.value = []

    // Use guest endpoint for unauthenticated users
    if (!isAuthenticated.value) {
      // Ensure we have a session
      const effectiveSessionId = sessionId || guestSessionId

      for await (const event of api.chat.guestMessage(effectiveSessionId, message, ttsOptions)) {
        // Store session ID for subsequent messages
        if (event.session_id && !guestSessionId) {
          guestSessionId = event.session_id
          if (!currentSession.value) {
            currentSession.value = {
              id: event.session_id,
              title: '新对话',
              created_at: new Date().toISOString(),
            }
            sessions.value = [currentSession.value]
          }
        }

        // 处理rag_step事件
        if (event.type === 'rag_step') {
          const stepIndex = ragSteps.value.findIndex(s => s.step === event.step)
          const stepConfig = RAG_STEP_CONFIG[event.step] || { label: event.step, icon: '•' }

          if (stepIndex >= 0) {
            ragSteps.value[stepIndex] = {
              ...ragSteps.value[stepIndex],
              status: event.status,
              message: event.message,
            }
          } else {
            ragSteps.value.push({
              step: event.step,
              label: stepConfig.label,
              icon: stepConfig.icon,
              status: event.status,
              message: event.message,
            })
          }
        }

        yield event
      }
      return
    }

    // Authenticated flow
    for await (const event of api.chat.askStream(sessionId, message, ttsOptions)) {
      // 处理rag_step事件
      if (event.type === 'rag_step') {
        const stepIndex = ragSteps.value.findIndex(s => s.step === event.step)
        const stepConfig = RAG_STEP_CONFIG[event.step] || { label: event.step, icon: '•' }

        if (stepIndex >= 0) {
          // 更新现有步骤
          ragSteps.value[stepIndex] = {
            ...ragSteps.value[stepIndex],
            status: event.status,
            message: event.message,
          }
        } else {
          // 添加新步骤
          ragSteps.value.push({
            step: event.step,
            label: stepConfig.label,
            icon: stepConfig.icon,
            status: event.status,
            message: event.message,
          })
        }
      }

      yield event
    }
  }

  function resetRagSteps() {
    ragSteps.value = []
  }

  return {
    sessions,
    currentSession,
    messages,
    loading,
    streamingContent,
    thinkingStatus,
    ragSteps,
    error,
    fetchSessions,
    createSession,
    selectSession,
    fetchMessages,
    deleteSession,
    sendMessage,
    resetRagSteps,
  }
}
