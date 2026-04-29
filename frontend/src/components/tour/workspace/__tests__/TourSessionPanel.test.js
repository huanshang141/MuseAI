import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

const mockTourState = vi.hoisted(() => ({
  tourSession: { value: { id: 's1', persona: 'A' } },
  currentHall: { value: 'relic-hall' },
  currentExhibit: { value: { id: 'e1', name: '尖底瓶' } },
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
}))

vi.mock('../../../../composables/useTour.js', () => ({
  useTour: () => mockTourState,
}))

vi.mock('../../../../api/index.js', () => ({
  api: {
    exhibits: { list: vi.fn(async () => ({ ok: true, data: { exhibits: [] } })) },
  },
}))

import TourWorkspace from '../../TourWorkspace.vue'

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
