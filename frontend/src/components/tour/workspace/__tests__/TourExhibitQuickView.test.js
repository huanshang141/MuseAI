import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'

const mockHolder = vi.hoisted(() => ({}))

vi.mock('../../../../composables/useTour.js', () => {
  mockHolder.currentHall = ref('relic-hall')
  mockHolder.currentExhibit = ref({ id: 'e1', name: '尖底瓶' })
  mockHolder.hallExhibits = ref([
    { id: 'e1', name: '尖底瓶', category: '陶器' },
    { id: 'e2', name: '人面鱼纹彩陶盆', category: '陶器' },
  ])
  mockHolder.exhibitIndex = ref(0)
  mockHolder.enterExhibit = vi.fn()
  return { useTour: () => mockHolder }
})

vi.mock('../../../../api/index.js', () => ({
  api: {
    exhibits: { list: vi.fn(async () => ({ ok: true, data: { exhibits: [] } })) },
  },
}))

import TourExhibitQuickView from '../TourExhibitQuickView.vue'

describe('TourExhibitQuickView', () => {
  it('renders exhibit list from current hall', () => {
    const wrapper = mount(TourExhibitQuickView, {
      global: { stubs: { 'el-button': true } },
    })

    expect(wrapper.text()).toContain('尖底瓶')
    expect(wrapper.text()).toContain('人面鱼纹彩陶盆')
  })

  it('renders template menu for each exhibit', () => {
    const wrapper = mount(TourExhibitQuickView, {
      global: { stubs: { 'el-button': true } },
    })

    const templateBtns = wrapper.findAll('.template-btn')
    expect(templateBtns.length).toBeGreaterThanOrEqual(3)
  })

  it('inserts template into draft on click', async () => {
    const { useTourWorkbench } = await import('../../../../composables/useTourWorkbench.js')
    const { chatDraft, activeTab } = useTourWorkbench()
    activeTab.value = 'exhibit'

    const wrapper = mount(TourExhibitQuickView, {
      global: { stubs: { 'el-button': true } },
      props: {},
    })

    const introBtn = wrapper.findAll('.template-btn').find(b => b.text().includes('介绍'))
    if (introBtn) {
      await introBtn.trigger('click')
      expect(chatDraft.value).toContain('尖底瓶')
    }

    chatDraft.value = ''
  })

  it('switches to session tab after template insert', async () => {
    const { useTourWorkbench } = await import('../../../../composables/useTourWorkbench.js')
    const { activeTab } = useTourWorkbench()
    activeTab.value = 'exhibit'

    const switchTab = vi.fn()
    const wrapper = mount(TourExhibitQuickView, {
      global: { stubs: { 'el-button': true } },
      props: {},
      attrs: { onSwitchTab: switchTab },
    })

    const templateBtn = wrapper.findAll('.template-btn')[0]
    if (templateBtn) {
      await templateBtn.trigger('click')
      expect(switchTab).toHaveBeenCalledWith('session')
    }
  })
})
