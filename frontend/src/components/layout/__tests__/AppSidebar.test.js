import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { ref, computed } from 'vue'

// Create reactive mock values
const mockUser = ref(null)
const mockIsAuthenticated = computed(() => !!mockUser.value)

vi.mock('../../../composables/useAuth.js', () => ({
  useAuth: () => ({
    user: mockUser,
    isAuthenticated: mockIsAuthenticated,
    userRole: ref(null),
    isAdmin: computed(() => false),
    setAuth: vi.fn(),
    clearAuth: vi.fn(),
    register: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
    getToken: vi.fn(() => null)
  })
}))

// Mock child components
vi.mock('../../knowledge/DocumentUpload.vue', () => ({
  default: {
    template: '<div class="mock-document-upload">DocumentUpload</div>'
  }
}))

vi.mock('../../knowledge/DocumentList.vue', () => ({
  default: {
    template: '<div class="mock-document-list">DocumentList</div>'
  }
}))

// Import after mocking
import AppSidebar from '../AppSidebar.vue'

// Element Plus stubs
const elementPlusStubs = {
  'el-empty': {
    template: '<div class="el-empty"><slot /></div>',
    props: ['description', 'image-size']
  },
  'el-button': {
    template: '<button class="el-button" @click="$emit(\'click\')"><slot /></button>',
    props: ['type', 'size']
  },
  'el-icon': {
    template: '<span class="el-icon"><slot /></span>'
  },
  'el-divider': {
    template: '<hr class="el-divider" />'
  },
  'el-alert': {
    template: '<div class="el-alert"><slot /></div>',
    props: ['title', 'type', 'closable']
  },
  'el-menu': {
    template: '<ul class="el-menu"><slot /></ul>',
    props: ['default-active', 'router']
  },
  'el-menu-item': {
    template: '<li class="el-menu-item"><slot /></li>',
    props: ['index']
  }
}

describe('AppSidebar', () => {
  let router

  beforeEach(() => {
    vi.clearAllMocks()
    // Reset to unauthenticated state
    mockUser.value = null

    router = createRouter({
      history: createWebHistory(),
      routes: [
        { path: '/', component: { template: '<div>Home</div>' } },
        { path: '/curator', component: { template: '<div>Curator</div>' } },
        { path: '/exhibits', component: { template: '<div>Exhibits</div>' } },
        { path: '/admin', component: { template: '<div>Admin</div>' } },
        { path: '/admin/exhibits', component: { template: '<div>Admin Exhibits</div>' } },
        { path: '/admin/halls', component: { template: '<div>Admin Halls</div>' } },
        { path: '/admin/documents', component: { template: '<div>Admin Documents</div>' } },
        { path: '/admin/tour-paths', component: { template: '<div>Admin Tour Paths</div>' } },
        { path: '/admin/prompts', component: { template: '<div>Admin Prompts</div>' } }
      ]
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders login button when not authenticated', async () => {
    // Ensure unauthenticated state
    mockUser.value = null

    const wrapper = mount(AppSidebar, {
      global: {
        plugins: [router],
        stubs: elementPlusStubs,
        provide: {
          showAuthModal: vi.fn()
        }
      }
    })

    await router.push('/')
    await router.isReady()
    await wrapper.vm.$nextTick()

    // Should show login prompt when not authenticated
    expect(wrapper.find('.el-empty').exists()).toBe(true)
    expect(wrapper.find('.el-button').exists()).toBe(true)
    expect(wrapper.find('.el-button').text()).toContain('登录')
  })

  it('clicking sidebar login calls injected showAuthModal', async () => {
    const showAuthModal = vi.fn()

    // Ensure unauthenticated state
    mockUser.value = null

    const wrapper = mount(AppSidebar, {
      global: {
        plugins: [router],
        stubs: elementPlusStubs,
        provide: {
          showAuthModal
        }
      }
    })

    await router.push('/')
    await router.isReady()
    await wrapper.vm.$nextTick()

    // Find and click the login button
    const loginButton = wrapper.find('.el-button')
    await loginButton.trigger('click')

    // Verify showAuthModal was called with true
    expect(showAuthModal).toHaveBeenCalledWith(true)
  })

  it('does not show knowledge base components on home route after migration', async () => {
    // Mock authenticated state
    mockUser.value = { email: 'test@example.com' }

    const wrapper = mount(AppSidebar, {
      global: {
        plugins: [router],
        stubs: elementPlusStubs,
        provide: {
          showAuthModal: vi.fn()
        }
      }
    })

    await router.push('/')
    await router.isReady()
    await wrapper.vm.$nextTick()

    // Knowledge base management has moved to /admin/documents
    expect(wrapper.find('.mock-document-upload').exists()).toBe(false)
    expect(wrapper.find('.mock-document-list').exists()).toBe(false)
    expect(wrapper.html()).not.toContain('知识库管理已迁移至管理后台。')
  })

  it('shows hall and knowledge menu entries in admin sidebar', async () => {
    mockUser.value = { email: 'admin@example.com' }

    const wrapper = mount(AppSidebar, {
      global: {
        plugins: [router],
        stubs: elementPlusStubs,
        provide: {
          showAuthModal: vi.fn()
        }
      }
    })

    await router.push('/admin')
    await router.isReady()
    await wrapper.vm.$nextTick()

    const html = wrapper.html()
    expect(html).toContain('知识库管理')
    expect(html).toContain('展厅设置')
  })
})