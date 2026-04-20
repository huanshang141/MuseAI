import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, h, nextTick, onMounted } from 'vue'
import ExhibitTour from '../ExhibitTour.vue'

const mockListExhibits = vi.hoisted(() => vi.fn())

const mockTourState = vi.hoisted(() => ({
    tourSession: { value: { id: 'session-1', persona: 'A' } },
    currentHall: { value: 'relic-hall' },
    currentExhibit: { value: null },
    hallExhibits: { value: [] },
    exhibitIndex: { value: 0 },
    enterExhibit: vi.fn(),
    completeHall: vi.fn(),
    tourStep: { value: 'tour' },
    bufferEvent: vi.fn(),
}))

vi.mock('../../../api/index.js', () => ({
    api: {
        exhibits: {
            list: mockListExhibits,
        },
    },
}))

vi.mock('../../../composables/useTour.js', () => ({
    useTour: () => mockTourState,
}))

function flushPromises() {
    return new Promise((resolve) => setTimeout(resolve, 0))
}

describe('ExhibitTour', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        mockTourState.exhibitIndex.value = 0
        mockTourState.currentHall.value = 'relic-hall'
    })

    it('mounts HallIntro only once while exhibits are loading', async () => {
        let resolveList
        mockListExhibits.mockImplementation(
            () => new Promise((resolve) => {
                resolveList = resolve
            }),
        )

        let hallIntroMountCount = 0
        const HallIntroStub = defineComponent({
            name: 'HallIntro',
            setup() {
                onMounted(() => {
                    hallIntroMountCount += 1
                })
                return () => h('div', { class: 'hall-intro-stub' }, 'HallIntro')
            },
        })

        mount(ExhibitTour, {
            global: {
                stubs: {
                    HallIntro: HallIntroStub,
                    ExhibitChat: { template: '<div class="exhibit-chat-stub" />' },
                    ExhibitNavigator: { template: '<div class="exhibit-navigator-stub" />' },
                    'el-icon': { template: '<span><slot /></span>' },
                    Loading: { template: '<span />' },
                },
            },
        })

        await nextTick()
        resolveList({ ok: true, data: { exhibits: [] } })
        await flushPromises()

        expect(hallIntroMountCount).toBe(1)
    })
})