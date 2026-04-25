import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ChatMainArea from '../ChatMainArea.vue'

describe('ChatMainArea', () => {
  it('does not render embedded session list', () => {
    const wrapper = mount(ChatMainArea, {
      global: {
        stubs: ['MessageItem', 'SourceCard'],
      },
    })

    expect(wrapper.find('.chat-session-pane').exists()).toBe(false)
  })
})
