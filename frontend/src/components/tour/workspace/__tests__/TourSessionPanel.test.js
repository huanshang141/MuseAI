import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'

const mockHolder = vi.hoisted(() => ({}))

vi.mock('../../../../composables/useTour.js', () => {
  mockHolder.tourSession = ref({ id: 's1', persona: 'A' })
  mockHolder.currentHall = ref('relic-hall')
  mockHolder.currentExhibit = ref({ id: 'e1', name: '尖底瓶' })
  mockHolder.hallExhibits = ref([])
  mockHolder.exhibitIndex = ref(0)
  mockHolder.chatMessages = ref([])
  mockHolder.streamingContent = ref('')
  mockHolder.loading = ref({ chat: false })
  mockHolder.suggestedActions = ref(null)
  mockHolder.personaLabel = ref('考古队长')
  mockHolder.enterExhibit = vi.fn()
  mockHolder.completeHall = vi.fn()
  mockHolder.sendTourMessage = vi.fn()
  mockHolder.bufferEvent = vi.fn()
  return {
    useTour: () => mockHolder,
  }
})

vi.mock('../../../../api/index.js', () => ({
  api: {
    exhibits: { list: vi.fn(async () => ({ ok: true, data: { exhibits: [] } })) },
  },
}))

import TourWorkspace from '../../TourWorkspace.vue'
import TourSessionPanel from '../TourSessionPanel.vue'

describe('TourWorkspace layout', () => {
  it('renders sidebar and secondary tabs', () => {
    const wrapper = mount(TourWorkspace, {
      global: {
        stubs: {
          TourWorkspaceSidebar: { template: '<div data-testid="tour-workspace-sidebar" />' },
          TourSecondaryTabs: { template: '<div data-testid="tour-secondary-tabs" />' },
        },
      },
    })

    expect(wrapper.find('[data-testid="tour-workspace-sidebar"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="tour-secondary-tabs"]').exists()).toBe(true)
  })

  it('renders active tab panel area', () => {
    const wrapper = mount(TourWorkspace, {
      global: {
        stubs: {
          TourWorkspaceSidebar: { template: '<div />' },
          TourSecondaryTabs: { template: '<div data-testid="tour-secondary-tabs" />' },
          TourSessionPanel: { template: '<div data-testid="tour-session-panel" />' },
        },
      },
    })

    expect(wrapper.find('[data-testid="tour-secondary-tabs"]').exists()).toBe(true)
  })
})

describe('TourSessionPanel', () => {
  const globalStubs = {
    'el-input': {
      props: ['modelValue', 'placeholder', 'disabled'],
      template: '<div class="el-input-stub"><input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" @keyup.enter="$emit(\'keyup-enter\')" /><slot name="append" /></div>',
    },
    'el-button': {
      props: ['loading'],
      template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>',
    },
  }

  it('renders input and send button', () => {
    const wrapper = mount(TourSessionPanel, { global: { stubs: globalStubs } })

    expect(wrapper.find('.el-input-stub').exists()).toBe(true)
    expect(wrapper.find('.el-button-stub').exists()).toBe(true)
  })

  it('shows streaming content when present', () => {
    mockHolder.streamingContent.value = '正在生成回答...'
    mockHolder.loading.value = { chat: true }

    const wrapper = mount(TourSessionPanel, { global: { stubs: globalStubs } })

    expect(wrapper.find('.streaming-content').exists()).toBe(true)
    expect(wrapper.find('.streaming-content').text()).toContain('正在生成回答...')

    mockHolder.streamingContent.value = ''
    mockHolder.loading.value = { chat: false }
  })

  it('preserves draft when switching tabs', async () => {
    const wrapper = mount(TourSessionPanel, { global: { stubs: globalStubs } })

    const input = wrapper.find('input')
    await input.setValue('我的草稿内容')

    const { useTourWorkbench } = await import('../../../../composables/useTourWorkbench.js')
    const { chatDraft, activeTab } = useTourWorkbench()
    expect(chatDraft.value).toBe('我的草稿内容')

    activeTab.value = 'settings'
    await wrapper.vm.$nextTick()
    activeTab.value = 'session'
    await wrapper.vm.$nextTick()

    expect(chatDraft.value).toBe('我的草稿内容')
  })
})
