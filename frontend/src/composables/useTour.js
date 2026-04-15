import { ref, computed } from 'vue'
import { api } from '../api/index.js'
import { useAuth } from './useAuth.js'

const tourSession = ref(null)
const sessionToken = ref(null)
const tourStep = ref('onboarding')
const currentHall = ref(null)
const currentExhibit = ref(null)
const hallExhibits = ref([])
const exhibitIndex = ref(0)
const streamingContent = ref('')
const suggestedActions = ref(null)
const chatMessages = ref([])
const loading = ref({ session: false, chat: false, report: false })
const error = ref(null)
const tourReport = ref(null)
const halls = ref([])

let eventBuffer = []
let eventFlushTimer = null
let exhibitStartTime = null

const EVENT_FLUSH_INTERVAL = 30000

const STORAGE_KEY_SESSION = 'tour_session_id'
const STORAGE_KEY_TOKEN = 'tour_session_token'
const STORAGE_KEY_EVENTS = 'tour_pending_events'

function _getToken() {
  return sessionToken.value || null
}

function _persistSession() {
  if (tourSession.value) {
    localStorage.setItem(STORAGE_KEY_SESSION, tourSession.value.id)
    localStorage.setItem(STORAGE_KEY_TOKEN, sessionToken.value || '')
  }
}

function _persistEvents() {
  localStorage.setItem(STORAGE_KEY_EVENTS, JSON.stringify(eventBuffer))
}

export function useTour() {
  const { isAuthenticated } = useAuth()

  async function createTourSession(interestType, persona, assumption) {
    loading.value.session = true
    error.value = null
    const guestId = isAuthenticated.value ? null : `guest-${crypto.randomUUID()}`
    const result = await api.tour.createSession({
      interest_type: interestType,
      persona,
      assumption,
      guest_id: guestId,
    })
    loading.value.session = false

    if (!result.ok) {
      error.value = result.data?.detail || '创建导览会话失败'
      return null
    }

    tourSession.value = result.data
    sessionToken.value = result.data.session_token
    _persistSession()
    return result.data
  }

  async function restoreSession() {
    const storedId = localStorage.getItem(STORAGE_KEY_SESSION)
    const storedToken = localStorage.getItem(STORAGE_KEY_TOKEN)
    if (!storedId) return false

    const result = await api.tour.getSession(storedId, storedToken)
    if (!result.ok) {
      localStorage.removeItem(STORAGE_KEY_SESSION)
      localStorage.removeItem(STORAGE_KEY_TOKEN)
      return false
    }

    tourSession.value = result.data
    sessionToken.value = storedToken

    if (result.data.status === 'completed') {
      tourStep.value = 'report'
    } else if (result.data.status === 'touring') {
      tourStep.value = 'tour'
      currentHall.value = result.data.current_hall
    } else if (result.data.status === 'opening') {
      tourStep.value = 'opening'
    }
    return true
  }

  async function fetchHalls() {
    const result = await api.tour.getHalls()
    if (result.ok) {
      halls.value = result.data.halls || []
    }
    return halls.value
  }

  async function selectHall(hallSlug) {
    currentHall.value = hallSlug
    const token = _getToken()
    await api.tour.updateSession(tourSession.value.id, {
      current_hall: hallSlug,
      status: 'touring',
    }, token)
    _persistSession()
  }

  async function enterExhibit(exhibit) {
    if (currentExhibit.value && exhibitStartTime) {
      const duration = Math.floor((Date.now() - exhibitStartTime) / 1000)
      bufferEvent('exhibit_view', {
        exhibit_id: currentExhibit.value.id,
        duration_seconds: duration,
      })
    }
    currentExhibit.value = exhibit
    exhibitStartTime = Date.now()
    chatMessages.value = []
    streamingContent.value = ''
    suggestedActions.value = null

    const token = _getToken()
    await api.tour.updateSession(tourSession.value.id, {
      current_exhibit_id: exhibit.id,
    }, token)
  }

  async function sendTourMessage(message) {
    if (!tourSession.value) return
    loading.value.chat = true
    chatMessages.value.push({ role: 'user', content: message })
    streamingContent.value = ''
    suggestedActions.value = null

    const token = _getToken()
    try {
      for await (const event of api.tour.chatStream(
        tourSession.value.id,
        message,
        token,
        currentExhibit.value?.id,
      )) {
        if (event.event === 'chunk' && event.data?.content) {
          streamingContent.value += event.data.content
        } else if (event.event === 'done') {
          chatMessages.value.push({ role: 'assistant', content: streamingContent.value })
          streamingContent.value = ''
          if (event.is_ceramic_question !== undefined || event.suggested_actions) {
            suggestedActions.value = event.suggested_actions || {}
            suggestedActions.value.is_ceramic_question = event.is_ceramic_question || false
          }
        } else if (event.event === 'error') {
          error.value = event.data?.message || 'AI导览暂时不可用'
        }
      }
    } catch (e) {
      console.error('Tour chat stream error:', e)
      error.value = '连接中断，请重试'
    }
    loading.value.chat = false
  }

  function bufferEvent(eventType, metadata = {}) {
    eventBuffer.push({
      event_type: eventType,
      exhibit_id: currentExhibit.value?.id || metadata.exhibit_id,
      hall: currentHall.value,
      duration_seconds: metadata.duration_seconds,
      metadata,
    })
    _persistEvents()
    if (!eventFlushTimer) {
      eventFlushTimer = setInterval(flushEvents, EVENT_FLUSH_INTERVAL)
    }
  }

  async function flushEvents() {
    if (eventBuffer.length === 0 || !tourSession.value) return
    const events = [...eventBuffer]
    eventBuffer = []
    _persistEvents()

    const token = _getToken()
    const result = await api.tour.recordEvents(tourSession.value.id, events, token)
    if (!result.ok) {
      eventBuffer = [...events, ...eventBuffer]
      _persistEvents()
    }
  }

  async function completeHall() {
    if (!tourSession.value) return
    await flushEvents()

    const token = _getToken()
    const result = await api.tour.completeHall(tourSession.value.id, token)
    if (result.ok) {
      if (result.data.all_halls_visited) {
        tourStep.value = 'report'
      } else {
        tourStep.value = 'hall-select'
        currentHall.value = null
        currentExhibit.value = null
      }
    }
    return result
  }

  async function generateReport() {
    if (!tourSession.value) return
    loading.value.report = true
    const token = _getToken()
    const result = await api.tour.generateReport(tourSession.value.id, token)
    loading.value.report = false
    if (result.ok) {
      tourReport.value = result.data
    } else {
      error.value = result.data?.detail || '报告生成失败'
    }
    return result
  }

  function resetTour() {
    tourSession.value = null
    sessionToken.value = null
    tourStep.value = 'onboarding'
    currentHall.value = null
    currentExhibit.value = null
    hallExhibits.value = []
    exhibitIndex.value = 0
    streamingContent.value = ''
    suggestedActions.value = null
    chatMessages.value = []
    tourReport.value = null
    error.value = null
    eventBuffer = []
    exhibitStartTime = null
    localStorage.removeItem(STORAGE_KEY_SESSION)
    localStorage.removeItem(STORAGE_KEY_TOKEN)
    localStorage.removeItem(STORAGE_KEY_EVENTS)
    if (eventFlushTimer) {
      clearInterval(eventFlushTimer)
      eventFlushTimer = null
    }
  }

  function setupBeforeUnload() {
    window.addEventListener('beforeunload', () => {
      if (eventBuffer.length > 0 && tourSession.value) {
        const token = _getToken()
        navigator.sendBeacon(
          `/api/v1/tour/sessions/${tourSession.value.id}/events`,
          JSON.stringify({ events: eventBuffer }),
        )
      }
    })
  }

  const personaLabel = computed(() => {
    const map = { A: '考古队长', B: '半坡原住民', C: '历史老师' }
    return map[tourSession.value?.persona] || ''
  })

  const reportThemeTitle = computed(() => {
    const map = { A: '你的半坡考古报告', B: '半坡一日穿越体验', C: '半坡游学荣誉证书' }
    return map[tourSession.value?.persona] || ''
  })

  return {
    tourSession,
    sessionToken,
    tourStep,
    currentHall,
    currentExhibit,
    hallExhibits,
    exhibitIndex,
    streamingContent,
    suggestedActions,
    chatMessages,
    loading,
    error,
    tourReport,
    halls,
    personaLabel,
    reportThemeTitle,
    createTourSession,
    restoreSession,
    fetchHalls,
    selectHall,
    enterExhibit,
    sendTourMessage,
    bufferEvent,
    flushEvents,
    completeHall,
    generateReport,
    resetTour,
    setupBeforeUnload,
  }
}
