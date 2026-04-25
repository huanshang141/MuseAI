import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AppSidebar from '../AppSidebar.vue'

const stubs = {
  ChatSessionsSidebar: { template: '<div class="chat-sessions">chat-sessions</div>' },
  ExhibitFilterSidebar: { template: '<div class="exhibit-filters">exhibit-filters</div>' },
  TourPlanSidebar: { template: '<div class="tour-plan">tour-plan</div>' },
  AdminNavSidebar: { template: '<div class="admin-nav">admin-nav</div>' },
}

describe('AppSidebar', () => {
  it('renders chat sidebar when type=chat-sessions', () => {
    const wrapper = mount(AppSidebar, {
      props: { type: 'chat-sessions' },
      global: { stubs },
    })

    expect(wrapper.html()).toContain('chat-sessions')
    expect(wrapper.find('.chat-sessions').exists()).toBe(true)
  })

  it('renders exhibit filters sidebar when type=exhibit-filters', () => {
    const wrapper = mount(AppSidebar, {
      props: { type: 'exhibit-filters' },
      global: { stubs },
    })

    expect(wrapper.find('.exhibit-filters').exists()).toBe(true)
  })

  it('renders tour plan sidebar when type=tour-plan', () => {
    const wrapper = mount(AppSidebar, {
      props: { type: 'tour-plan' },
      global: { stubs },
    })

    expect(wrapper.find('.tour-plan').exists()).toBe(true)
  })

  it('renders admin nav sidebar when type=admin-nav', () => {
    const wrapper = mount(AppSidebar, {
      props: { type: 'admin-nav' },
      global: { stubs },
    })

    expect(wrapper.find('.admin-nav').exists()).toBe(true)
  })
})
