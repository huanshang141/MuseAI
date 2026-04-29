import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

vi.mock('../../../../composables/useTour.js', () => ({
  useTour: () => ({
    tourSession: { value: { id: 's1' } },
    currentHall: { value: 'relic-hall' },
    currentExhibit: { value: null },
    hallExhibits: { value: [] },
    exhibitIndex: { value: 0 },
    chatMessages: { value: [] },
    streamingContent: { value: '' },
    loading: { value: { chat: false } },
    suggestedActions: { value: null },
    enterExhibit: vi.fn(),
    completeHall: vi.fn(),
    sendTourMessage: vi.fn(),
    bufferEvent: vi.fn(),
    personaLabel: { value: '考古队长' },
  }),
}))

vi.mock('../../../../api/index.js', () => ({
  api: {
    exhibits: { list: vi.fn(async () => ({ ok: true, data: { exhibits: [] } })) },
  },
}))

import TourSettingsPanel from '../TourSettingsPanel.vue'

describe('TourSettingsPanel', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.resetModules()
  })

  const globalStubs = {
    'el-select': {
      props: ['modelValue'],
      template: '<select :value="modelValue" @change="$emit(\'update:modelValue\', $event.target.value)"><slot /></select>',
    },
    'el-option': {
      props: ['label', 'value'],
      template: '<option :value="value">{{ label }}</option>',
    },
    'el-switch': {
      props: ['modelValue'],
      template: '<input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" />',
    },
    'el-button': {
      template: '<button @click="$emit(\'click\')"><slot /></button>',
    },
  }

  it('renders UI preferences section', () => {
    const wrapper = mount(TourSettingsPanel, { global: { stubs: globalStubs } })

    expect(wrapper.text()).toContain('界面偏好')
    expect(wrapper.text()).toContain('字体大小')
    expect(wrapper.text()).toContain('消息密度')
  })

  it('renders style preferences section', () => {
    const wrapper = mount(TourSettingsPanel, { global: { stubs: globalStubs } })

    expect(wrapper.text()).toContain('风格偏好')
    expect(wrapper.text()).toContain('回答长度')
    expect(wrapper.text()).toContain('讲解深浅')
    expect(wrapper.text()).toContain('术语难度')
  })

  it('renders TTS placeholder section', () => {
    const wrapper = mount(TourSettingsPanel, { global: { stubs: globalStubs } })

    expect(wrapper.text()).toContain('语音朗读')
    expect(wrapper.text()).toContain('即将推出')
  })

  it('renders reset button', () => {
    const wrapper = mount(TourSettingsPanel, { global: { stubs: globalStubs } })

    expect(wrapper.find('[data-testid="reset-prefs-btn"]').exists()).toBe(true)
  })
})
