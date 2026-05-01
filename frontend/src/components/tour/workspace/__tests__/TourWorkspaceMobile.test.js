import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { BREAKPOINTS } from '../../../../design-system/tokens/breakpoints.js'

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
  return { useTour: () => mockHolder }
})

vi.mock('../../../../api/index.js', () => ({
  api: {
    exhibits: { list: vi.fn(async () => ({ ok: true, data: { exhibits: [] } })) },
  },
}))

const mediaQueryHolder = vi.hoisted(() => ({ ref: null }))

vi.mock('../../../../composables/useMediaQuery.js', () => {
  // eslint-disable-next-line no-undef
  const { ref } = require('vue')
  mediaQueryHolder.ref = ref(true)
  return {
    useMediaQuery: () => mediaQueryHolder.ref,
  }
})

import TourWorkspace from '../../TourWorkspace.vue'

describe('TourWorkspace mobile', () => {
  it('hides sidebar on narrow viewport', () => {
    mediaQueryHolder.ref.value = false

    const wrapper = mount(TourWorkspace, {
      global: {
        stubs: {
          TourWorkspaceSidebar: { template: '<div data-testid="sidebar" />' },
          TourSecondaryTabs: { template: '<div data-testid="tabs" />' },
          TourSessionPanel: true,
          TourExhibitQuickView: true,
          TourProgressPanel: true,
          TourSettingsPanel: true,
        },
      },
    })

    expect(wrapper.find('[data-testid="sidebar"]').exists()).toBe(false)
  })

  it('shows sidebar on wide viewport', () => {
    mediaQueryHolder.ref.value = true

    const wrapper = mount(TourWorkspace, {
      global: {
        stubs: {
          TourWorkspaceSidebar: { template: '<div data-testid="sidebar" />' },
          TourSecondaryTabs: { template: '<div data-testid="tabs" />' },
          TourSessionPanel: true,
          TourExhibitQuickView: true,
          TourProgressPanel: true,
          TourSettingsPanel: true,
        },
      },
    })

    expect(wrapper.find('[data-testid="sidebar"]').exists()).toBe(true)
  })
})
