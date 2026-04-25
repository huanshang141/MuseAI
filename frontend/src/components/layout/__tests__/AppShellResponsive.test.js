import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { computed, ref } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import AppHeader from '../AppHeader.vue'

vi.mock('../../../composables/useAuth.js', () => ({
  useAuth: () => ({
    user: ref({ email: 'test@example.com' }),
    isAuthenticated: computed(() => true),
    isAdmin: computed(() => false),
    logout: vi.fn(async () => ({})),
  }),
}))

vi.mock('../../../api/index.js', () => ({
  api: {
    health: vi.fn(async () => ({ ok: true })),
  },
}))

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: { template: '<div>home</div>' } }],
  })
}

describe('App shell responsive behavior', () => {
  it('emits toggle-sidebar when mobile menu button is clicked', async () => {
    const router = createTestRouter()
    await router.push('/')
    await router.isReady()

    const wrapper = mount(AppHeader, {
      props: { showSidebarToggle: true },
      global: {
        plugins: [router],
        stubs: {
          FishFaceSymbol: true,
          AuthModal: true,
          'el-menu': true,
          'el-menu-item': true,
          'el-icon': true,
          'el-tag': true,
          'el-dropdown': true,
          'el-dropdown-menu': true,
          'el-dropdown-item': true,
          'el-button': {
            template: '<button class="el-button" @click="$emit(\'click\')"><slot /></button>',
          },
        },
      },
    })

    const toggleButton = wrapper.find('[data-testid="sidebar-toggle"]')
    expect(toggleButton.exists()).toBe(true)

    await toggleButton.trigger('click')

    expect(wrapper.emitted('toggle-sidebar')).toBeTruthy()
  })
})
