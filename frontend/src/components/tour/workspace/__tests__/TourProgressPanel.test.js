import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ref } from 'vue'

const mockHolder = vi.hoisted(() => ({}))

vi.mock('../../../../composables/useTour.js', () => {
  mockHolder.tourSession = ref({ id: 's1', persona: 'A', visited_exhibit_ids: ['e1', 'e2'] })
  mockHolder.currentHall = ref('relic-hall')
  mockHolder.currentExhibit = ref({ id: 'e2', name: '人面鱼纹彩陶盆' })
  mockHolder.hallExhibits = ref([
    { id: 'e1', name: '尖底瓶' },
    { id: 'e2', name: '人面鱼纹彩陶盆' },
    { id: 'e3', name: '红陶钵' },
  ])
  mockHolder.exhibitIndex = ref(1)
  mockHolder.visitedHalls = ref(['relic-hall'])
  mockHolder.completeHall = vi.fn()
  return { useTour: () => mockHolder }
})

vi.mock('../../../../api/index.js', () => ({
  api: {
    exhibits: { list: vi.fn(async () => ({ ok: true, data: { exhibits: [] } })) },
  },
}))

import TourProgressPanel from '../TourProgressPanel.vue'

describe('TourProgressPanel', () => {
  it('renders hall progress', () => {
    const wrapper = mount(TourProgressPanel, {
      global: { stubs: { 'el-button': true, 'el-progress': true } },
    })

    expect(wrapper.text()).toContain('展厅')
    expect(wrapper.text()).toContain('展品')
  })

  it('shows visited exhibits count', () => {
    const wrapper = mount(TourProgressPanel, {
      global: { stubs: { 'el-button': true, 'el-progress': true } },
    })

    expect(wrapper.text()).toContain('2/3')
  })

  it('shows complete hall button', () => {
    const wrapper = mount(TourProgressPanel, {
      global: { stubs: { 'el-button': true, 'el-progress': true } },
    })

    expect(wrapper.find('[data-testid="complete-hall-btn"]').exists()).toBe(true)
  })

  it('calls completeHall on button click', async () => {
    const wrapper = mount(TourProgressPanel, {
      global: { stubs: { 'el-button': { template: '<button data-testid="complete-hall-btn" @click="$emit(\'click\')"><slot /></button>' } } },
    })

    await wrapper.find('[data-testid="complete-hall-btn"]').trigger('click')
    expect(mockHolder.completeHall).toHaveBeenCalled()
  })
})
