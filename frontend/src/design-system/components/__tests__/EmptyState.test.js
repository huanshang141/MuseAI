import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import EmptyState from '../EmptyState.vue'

describe('EmptyState', () => {
  it('renders jar motif when icon=jar', () => {
    const wrapper = mount(EmptyState, {
      props: {
        icon: 'jar',
        title: '空',
        description: '空状态',
      },
      global: {
        stubs: ['PointedJar', 'FishFaceBasin', 'FishSwim'],
      },
    })

    expect(wrapper.text()).toContain('空状态')
  })
})
