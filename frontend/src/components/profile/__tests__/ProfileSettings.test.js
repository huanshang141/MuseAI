import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ProfileSettings from '../ProfileSettings.vue'

// Mock the api module
vi.mock('../../../api/index.js', () => ({
  api: {
    profile: {
      get: vi.fn(),
      update: vi.fn()
    }
  }
}))

// Mock Element Plus message
vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    error: vi.fn()
  }
}))

// Import the mocked api
import { api } from '../../../api/index.js'

describe('ProfileSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    // Default mock for profile.get
    api.profile.get.mockResolvedValue({
      ok: true,
      data: {
        interests: ['bronze', 'painting'],
        knowledge_level: 'beginner',
        narrative_preference: 'storytelling',
        reflection_depth: 3
      }
    })

    api.profile.update.mockResolvedValue({
      ok: true,
      data: {}
    })
  })

  it('profile settings uses centralized api.profile methods', async () => {
    const wrapper = mount(ProfileSettings, {
      global: {
        stubs: {
          'el-card': {
            template: '<div class="el-card"><slot /></div>',
            props: ['v-loading']
          },
          'el-form': {
            template: '<form class="el-form"><slot /></form>',
            props: ['label-position', 'model']
          },
          'el-form-item': {
            template: '<div class="el-form-item"><slot /></div>',
            props: ['label']
          },
          'el-checkbox-group': {
            template: '<div class="el-checkbox-group"><slot /></div>',
            props: ['modelValue']
          },
          'el-checkbox': {
            template: '<label class="el-checkbox"><slot /></label>',
            props: ['label']
          },
          'el-radio-group': {
            template: '<div class="el-radio-group"><slot /></div>',
            props: ['modelValue']
          },
          'el-radio': {
            template: '<label class="el-radio"><slot /></label>',
            props: ['label']
          },
          'el-slider': {
            template: '<input type="range" class="el-slider" />',
            props: ['modelValue', 'min', 'max', 'step', 'show-stops']
          },
          'el-button': {
            template: '<button class="el-button" type="button" @click="$emit(\'click\')"><slot /></button>',
            props: ['type', 'loading']
          }
        },
        directives: {
          loading: () => {} // Stub v-loading directive
        }
      }
    })

    // Wait for onMounted to complete
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 50))

    // Verify that api.profile.get was called on mount
    expect(api.profile.get).toHaveBeenCalled()

    // Find and trigger save
    const saveButton = wrapper.find('.el-button')
    expect(saveButton.exists()).toBe(true)
    await saveButton.trigger('click')
    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 50))

    // Verify that api.profile.update was called
    expect(api.profile.update).toHaveBeenCalled()
  })

  it('loads profile data on mount using api.profile.get', async () => {
    const wrapper = mount(ProfileSettings, {
      global: {
        stubs: {
          'el-card': { template: '<div><slot /></div>' },
          'el-form': { template: '<form><slot /></form>', props: ['model'] },
          'el-form-item': { template: '<div><slot /></div>' },
          'el-checkbox-group': { template: '<div><slot /></div>', props: ['modelValue'] },
          'el-checkbox': { template: '<label><slot /></label>' },
          'el-radio-group': { template: '<div><slot /></div>', props: ['modelValue'] },
          'el-radio': { template: '<label><slot /></label>' },
          'el-slider': { template: '<input type="range" />', props: ['modelValue'] },
          'el-button': { template: '<button><slot /></button>' }
        },
        directives: {
          loading: () => {}
        }
      }
    })

    await wrapper.vm.$nextTick()
    await new Promise(resolve => setTimeout(resolve, 50))

    expect(api.profile.get).toHaveBeenCalledTimes(1)
  })
})
