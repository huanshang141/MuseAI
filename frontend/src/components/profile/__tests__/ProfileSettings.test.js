import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ProfileSettings from '../ProfileSettings.vue'

vi.mock('../../../api/index.js', () => ({
  api: {
    profile: {
      get: vi.fn(),
      update: vi.fn(),
    },
  },
}))

vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

import { api } from '../../../api/index.js'

describe('ProfileSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks()

    api.profile.get.mockResolvedValue({
      ok: true,
      data: {
        interests: ['bronze', 'painting'],
        knowledge_level: 'beginner',
        narrative_preference: 'storytelling',
        reflection_depth: 3,
      },
    })

    api.profile.update.mockResolvedValue({
      ok: true,
      data: {},
    })
  })

  it('still calls api.profile.update after redesign', async () => {
    const wrapper = mount(ProfileSettings, {
      global: {
        stubs: {
          MuseumCard: { template: '<section><slot /></section>' },
          'el-card': { template: '<section><slot /></section>' },
          'el-form': { template: '<form><slot /></form>', props: ['model', 'label-position'] },
          'el-form-item': { template: '<div><slot /></div>', props: ['label'] },
          'el-checkbox-group': { template: '<div><slot /></div>', props: ['modelValue'] },
          'el-checkbox': { template: '<label><slot /></label>', props: ['label'] },
          'el-radio-group': { template: '<div><slot /></div>', props: ['modelValue'] },
          'el-radio': { template: '<label><slot /></label>', props: ['label'] },
          'el-slider': { template: '<input type="range" />', props: ['modelValue'] },
          'el-button': {
            template: '<button type="button" @click="$emit(\'click\')"><slot /></button>',
            props: ['type', 'loading'],
          },
        },
        directives: {
          loading: () => {},
        },
      },
    })

    await wrapper.vm.$nextTick()
    await new Promise((resolve) => setTimeout(resolve, 30))

    expect(api.profile.get).toHaveBeenCalledTimes(1)

    const saveButton = wrapper.find('[data-testid="profile-save"]')
    expect(saveButton.exists()).toBe(true)

    await saveButton.trigger('click')
    await wrapper.vm.$nextTick()
    await new Promise((resolve) => setTimeout(resolve, 30))

    expect(api.profile.update).toHaveBeenCalled()
  })
})
