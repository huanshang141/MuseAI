import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, computed, nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import App from '../../../App.vue'

vi.mock('../../../composables/useAuth.js', () => ({
  useAuth: () => ({
    user: ref(null),
    isAuthenticated: computed(() => false),
    isAdmin: computed(() => false),
    logout: vi.fn(async () => ({})),
  }),
}))

vi.mock('../../../api/index.js', () => ({
  api: {
    health: vi.fn(async () => ({ ok: true })),
  },
}))

vi.mock('../../../composables/useMediaQuery.js', () => ({
  useMediaQuery: () => ref(false),
}))

describe('TourViewWorkspaceGate', () => {
  it('keeps app header visible on /tour route', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/tour', component: { template: '<div>tour</div>' } }],
    })
    await router.push('/tour')
    await router.isReady()

    const wrapper = mount(App, {
      global: {
        plugins: [router],
        stubs: {
          AppHeader: { template: '<header data-testid="app-header">Header</header>' },
          AppSidebar: { template: '<aside data-testid="app-sidebar">Sidebar</aside>' },
          AuthModal: true,
          AppDrawer: {
            props: ['open', 'title'],
            template: '<div v-if="open"><slot /></div>',
          },
        },
      },
    })

    expect(wrapper.find('[data-testid="app-header"]').exists()).toBe(true)
  })
})

const mockHolder = vi.hoisted(() => ({ tourStep: null }))

vi.mock('../../../composables/useTour.js', () => {
  mockHolder.tourStep = ref('onboarding')
  return {
    useTour: () => ({
      tourStep: mockHolder.tourStep,
      restoreSession: vi.fn(async () => false),
      setupBeforeUnload: vi.fn(),
      resetTour: vi.fn(),
    }),
  }
})

import TourView from '../../../views/TourView.vue'

const stepStubs = {
  OnboardingQuiz: { template: '<div data-testid="onboarding" />' },
  OpeningNarrative: { template: '<div data-testid="opening" />' },
  HallSelect: { template: '<div data-testid="hall-select" />' },
  TourWorkspace: { template: '<div data-testid="tour-workspace" />' },
  TourReport: { template: '<div data-testid="report" />' },
}

describe('TourView step gating', () => {
  beforeEach(() => {
    if (mockHolder.tourStep) {
      mockHolder.tourStep.value = 'onboarding'
    }
  })

  const stepTests = [
    { step: 'onboarding', testid: 'onboarding', label: 'OnboardingQuiz' },
    { step: 'opening', testid: 'opening', label: 'OpeningNarrative' },
    { step: 'hall-select', testid: 'hall-select', label: 'HallSelect' },
    { step: 'tour', testid: 'tour-workspace', label: 'TourWorkspace' },
    { step: 'report', testid: 'report', label: 'TourReport' },
  ]

  for (const { step, testid, label } of stepTests) {
    it(`renders ${label} when tourStep is '${step}'`, async () => {
      mockHolder.tourStep.value = step
      const wrapper = mount(TourView, { global: { stubs: stepStubs } })

      expect(wrapper.find(`[data-testid="${testid}"]`).exists()).toBe(true)
      expect(wrapper.find('[data-testid="tour-workspace"]').exists()).toBe(step === 'tour')
    })
  }

  it('switches rendered component when tourStep changes', async () => {
    mockHolder.tourStep.value = 'hall-select'
    const wrapper = mount(TourView, { global: { stubs: stepStubs } })

    expect(wrapper.find('[data-testid="hall-select"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="tour-workspace"]').exists()).toBe(false)

    mockHolder.tourStep.value = 'tour'
    await nextTick()

    expect(wrapper.find('[data-testid="tour-workspace"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="hall-select"]').exists()).toBe(false)
  })
})
