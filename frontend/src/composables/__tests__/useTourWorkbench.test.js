import { describe, it, expect, beforeEach, vi } from 'vitest'
import { STORAGE_KEY_PREFIX } from '../useTourWorkbench.js'

describe('useTourWorkbench', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.resetModules()
  })

  it('returns default values on first use', async () => {
    const { useTourWorkbench } = await import('../useTourWorkbench.js')
    const { activeTab, chatDraft, uiPreferences, stylePreferences, ttsPreferences } = useTourWorkbench()

    expect(activeTab.value).toBe('session')
    expect(chatDraft.value).toBe('')
    expect(uiPreferences.value.fontScale).toBe('md')
    expect(uiPreferences.value.messageDensity).toBe('comfortable')
    expect(uiPreferences.value.autoScroll).toBe(true)
    expect(uiPreferences.value.showQuickPrompts).toBe(true)
    expect(uiPreferences.value.rememberDraft).toBe(true)
    expect(stylePreferences.value.answerLength).toBe('balanced')
    expect(stylePreferences.value.depth).toBe('standard')
    expect(stylePreferences.value.terminology).toBe('plain')
    expect(stylePreferences.value.enabled).toBe(true)
    expect(ttsPreferences.value.voice).toBe('female_warm')
    expect(ttsPreferences.value.speed).toBe('1x')
    expect(ttsPreferences.value.autoPlay).toBe(false)
  })

  it('buildStyledPrompt injects style hints above user message', async () => {
    const { useTourWorkbench } = await import('../useTourWorkbench.js')
    const { buildStyledPrompt } = useTourWorkbench()

    const result = buildStyledPrompt('介绍一下人面鱼纹彩陶盆', {
      answerLength: 'detailed',
      depth: 'deep',
      terminology: 'academic',
    })

    expect(result).toContain('回答长度')
    expect(result).toContain('详细')
    expect(result).toContain('讲解深浅')
    expect(result).toContain('深入')
    expect(result).toContain('术语难度')
    expect(result).toContain('学术')
    expect(result).toContain('介绍一下人面鱼纹彩陶盆')
  })

  it('buildStyledPrompt returns raw input when style is disabled', async () => {
    const { useTourWorkbench } = await import('../useTourWorkbench.js')
    const { buildStyledPrompt } = useTourWorkbench()

    const result = buildStyledPrompt('你好', { enabled: false })
    expect(result).toBe('你好')
  })

  it('buildStyledPrompt falls back to stylePreferences when no style arg', async () => {
    const { useTourWorkbench } = await import('../useTourWorkbench.js')
    const { buildStyledPrompt, stylePreferences } = useTourWorkbench()

    stylePreferences.value.answerLength = 'brief'
    const result = buildStyledPrompt('测试问题')

    expect(result).toContain('简短')
    expect(result).toContain('测试问题')
  })

  it('inserts exhibit template and keeps unsent draft', async () => {
    const { useTourWorkbench } = await import('../useTourWorkbench.js')
    const { chatDraft, insertTemplateForExhibit } = useTourWorkbench()

    const result = insertTemplateForExhibit({ id: '1', name: '尖底瓶' }, 'intro')
    expect(result).toBe(true)
    expect(chatDraft.value).toBe('介绍一下尖底瓶')
  })

  it('inserts controversy template', async () => {
    const { useTourWorkbench } = await import('../useTourWorkbench.js')
    const { chatDraft, insertTemplateForExhibit } = useTourWorkbench()

    insertTemplateForExhibit({ id: '1', name: '人面鱼纹彩陶盆' }, 'controversy')
    expect(chatDraft.value).toBe('人面鱼纹彩陶盆有什么历史争议？')
  })

  it('inserts relation template', async () => {
    const { useTourWorkbench } = await import('../useTourWorkbench.js')
    const { chatDraft, insertTemplateForExhibit } = useTourWorkbench()

    insertTemplateForExhibit({ id: '1', name: '尖底瓶' }, 'relation')
    expect(chatDraft.value).toBe('尖底瓶和其他展品有什么联系？')
  })

  it('insertTemplateForExhibit returns false for invalid inputs', async () => {
    const { useTourWorkbench } = await import('../useTourWorkbench.js')
    const { insertTemplateForExhibit } = useTourWorkbench()

    expect(insertTemplateForExhibit(null, 'intro')).toBe(false)
    expect(insertTemplateForExhibit({ id: '1' }, 'intro')).toBe(false)
    expect(insertTemplateForExhibit({ id: '1', name: '' }, 'intro')).toBe(false)
    expect(insertTemplateForExhibit({ id: '1', name: 'test' }, 'nonexistent')).toBe(false)
  })

  it('persists preferences to localStorage via watch', async () => {
    const { useTourWorkbench } = await import('../useTourWorkbench.js')
    const { uiPreferences } = useTourWorkbench()

    uiPreferences.value.fontScale = 'lg'
    await new Promise((r) => setTimeout(r, 0))

    const stored = JSON.parse(localStorage.getItem(`${STORAGE_KEY_PREFIX}ui_preferences`))
    expect(stored.fontScale).toBe('lg')
  })

  it('restores preferences from localStorage', async () => {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}ui_preferences`, JSON.stringify({
      fontScale: 'lg',
      messageDensity: 'compact',
      autoScroll: false,
      showQuickPrompts: false,
      rememberDraft: true,
    }))
    localStorage.setItem(`${STORAGE_KEY_PREFIX}style_preferences`, JSON.stringify({
      answerLength: 'brief',
      depth: 'introductory',
      terminology: 'academic',
      enabled: true,
    }))

    const { useTourWorkbench } = await import('../useTourWorkbench.js')
    const { uiPreferences, stylePreferences } = useTourWorkbench()

    expect(uiPreferences.value.fontScale).toBe('lg')
    expect(uiPreferences.value.messageDensity).toBe('compact')
    expect(stylePreferences.value.answerLength).toBe('brief')
    expect(stylePreferences.value.terminology).toBe('academic')
  })

  it('merges stored data with defaults for missing fields', async () => {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}ui_preferences`, JSON.stringify({
      fontScale: 'lg',
    }))

    const { useTourWorkbench } = await import('../useTourWorkbench.js')
    const { uiPreferences } = useTourWorkbench()

    expect(uiPreferences.value.fontScale).toBe('lg')
    expect(uiPreferences.value.messageDensity).toBe('comfortable')
    expect(uiPreferences.value.autoScroll).toBe(true)
  })

  it('resets preferences to defaults', async () => {
    const { useTourWorkbench } = await import('../useTourWorkbench.js')
    const { uiPreferences, stylePreferences, resetPreferences } = useTourWorkbench()

    uiPreferences.value.fontScale = 'lg'
    stylePreferences.value.depth = 'deep'
    resetPreferences()

    expect(uiPreferences.value.fontScale).toBe('md')
    expect(stylePreferences.value.depth).toBe('standard')
  })

  it('falls back to defaults on corrupt localStorage data', async () => {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}ui_preferences`, 'not-json')

    const { useTourWorkbench } = await import('../useTourWorkbench.js')
    const { uiPreferences } = useTourWorkbench()

    expect(uiPreferences.value.fontScale).toBe('md')
  })
})
