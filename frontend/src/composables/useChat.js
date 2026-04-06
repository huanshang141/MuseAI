import { ref } from 'vue'
import { api } from '../api/index.js'
import { useAuth } from './useAuth.js'

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

    sessions.value = result.data.sessions || result.data
    return result
  }

  async function createSession(title) {
    if (!isAuthenticated.value) {
      error.value = '请先登录'
      return { ok: false, status: 401, data: { detail: '未认证' } }
    }

    console.log('[useChat] Creating session with title:', title)
    const result = await api.chat.createSession(title)
    console.log('[useChat] Create session result:', result)

    if (!result.ok) {
      console.error('[useChat] Create session failed:', result)
      return handleError(result)
    }

    console.log('[useChat] Setting currentSession to:', result.data)
    sessions.value.unshift(result.data)
    currentSession.value = result.data
    messages.value = []
    console.log('[useChat] currentSession is now:', currentSession.value)
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

    messages.value = result.data.messages || result.data
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

    // 重置RAG步骤状态
    ragSteps.value = []

    for await (const event of api.chat.askStream(sessionId, message)) {
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
