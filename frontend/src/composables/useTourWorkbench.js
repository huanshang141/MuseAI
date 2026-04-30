import { ref, watch } from 'vue'

export const STORAGE_KEY_PREFIX = 'tour_workbench_'

const DEFAULT_UI_PREFERENCES = {
  fontScale: 'md',
  messageDensity: 'comfortable',
  autoScroll: true,
  showQuickPrompts: true,
  rememberDraft: true,
}

const DEFAULT_STYLE_PREFERENCES = {
  answerLength: 'balanced',
  depth: 'standard',
  terminology: 'plain',
  enabled: true,
}

const DEFAULT_TTS_PREFERENCES = {
  voice: 'female_warm',
  speed: '1x',
  autoPlay: false,
}

const EXHIBIT_TEMPLATES = {
  intro: (name) => `介绍一下${name}`,
  controversy: (name) => `${name}有什么历史争议？`,
  relation: (name) => `${name}和其他展品有什么联系？`,
}

const ANSWER_LENGTH_MAP = {
  brief: '简短',
  balanced: '适中',
  detailed: '详细',
}

const DEPTH_MAP = {
  introductory: '入门',
  standard: '标准',
  deep: '深入',
}

const TERMINOLOGY_MAP = {
  plain: '通俗',
  professional: '专业',
  academic: '学术',
}

function loadFromStorage(key, fallback) {
  try {
    const raw = localStorage.getItem(key)
    if (raw) return { ...fallback, ...JSON.parse(raw) }
  } catch {
    console.warn(`[useTourWorkbench] Failed to parse ${key}, using defaults`)
  }
  return { ...fallback }
}

function saveToStorage(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    console.warn(`[useTourWorkbench] Failed to persist ${key}`)
  }
}

const activeTab = ref('session')
const chatDraft = ref('')

const uiPreferences = ref(loadFromStorage(
  `${STORAGE_KEY_PREFIX}ui_preferences`,
  DEFAULT_UI_PREFERENCES,
))

const stylePreferences = ref(loadFromStorage(
  `${STORAGE_KEY_PREFIX}style_preferences`,
  DEFAULT_STYLE_PREFERENCES,
))

const ttsPreferences = ref(loadFromStorage(
  `${STORAGE_KEY_PREFIX}tts_preferences`,
  DEFAULT_TTS_PREFERENCES,
))

watch([uiPreferences, stylePreferences, ttsPreferences], () => {
  saveToStorage(`${STORAGE_KEY_PREFIX}ui_preferences`, uiPreferences.value)
  saveToStorage(`${STORAGE_KEY_PREFIX}style_preferences`, stylePreferences.value)
  saveToStorage(`${STORAGE_KEY_PREFIX}tts_preferences`, ttsPreferences.value)
}, { deep: true })

export function useTourWorkbench() {
  function persistPreferences() {
    saveToStorage(`${STORAGE_KEY_PREFIX}ui_preferences`, uiPreferences.value)
    saveToStorage(`${STORAGE_KEY_PREFIX}style_preferences`, stylePreferences.value)
    saveToStorage(`${STORAGE_KEY_PREFIX}tts_preferences`, ttsPreferences.value)
  }

  function resetPreferences() {
    uiPreferences.value = { ...DEFAULT_UI_PREFERENCES }
    stylePreferences.value = { ...DEFAULT_STYLE_PREFERENCES }
    ttsPreferences.value = { ...DEFAULT_TTS_PREFERENCES }
  }

  function insertTemplateForExhibit(exhibit, templateKey) {
    const templateFn = EXHIBIT_TEMPLATES[templateKey]
    if (!templateFn || !exhibit?.name) return false
    chatDraft.value = templateFn(exhibit.name)
    return true
  }

  function buildStyledPrompt(rawInput, style) {
    const effectiveStyle = style ?? stylePreferences.value
    if (effectiveStyle.enabled === false) return rawInput

    const lines = ['[风格约束]']
    if (effectiveStyle.answerLength) {
      lines.push(`回答长度: ${ANSWER_LENGTH_MAP[effectiveStyle.answerLength] || effectiveStyle.answerLength}`)
    }
    if (effectiveStyle.depth) {
      lines.push(`讲解深浅: ${DEPTH_MAP[effectiveStyle.depth] || effectiveStyle.depth}`)
    }
    if (effectiveStyle.terminology) {
      lines.push(`术语难度: ${TERMINOLOGY_MAP[effectiveStyle.terminology] || effectiveStyle.terminology}`)
    }
    lines.push('---')
    lines.push(rawInput)
    return lines.join('\n')
  }

  function getStylePayload() {
    const s = stylePreferences.value
    if (s.enabled === false) return null
    const payload = {}
    if (s.answerLength) payload.answer_length = s.answerLength
    if (s.depth) payload.depth = s.depth
    if (s.terminology) payload.terminology = s.terminology
    return Object.keys(payload).length ? payload : null
  }

  return {
    activeTab,
    chatDraft,
    uiPreferences,
    stylePreferences,
    ttsPreferences,
    insertTemplateForExhibit,
    buildStyledPrompt,
    getStylePayload,
    persistPreferences,
    resetPreferences,
  }
}
