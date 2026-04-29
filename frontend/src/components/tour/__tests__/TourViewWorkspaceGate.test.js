import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref, computed } from 'vue'
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
