<script setup>
import { ref, onMounted, computed } from 'vue'
import { useTour } from '../../composables/useTour.js'
import { api } from '../../api/index.js'
import HallIntro from './HallIntro.vue'
import ExhibitChat from './ExhibitChat.vue'
import ExhibitNavigator from './ExhibitNavigator.vue'

const {
  tourSession, currentHall, currentExhibit, hallExhibits, exhibitIndex,
  enterExhibit, completeHall, tourStep, bufferEvent,
} = useTour()

const subStep = ref('hall-intro')
const exhibits = ref([])
const loadingExhibits = ref(false)

const hallNames = { 'relic-hall': '出土文物展厅', 'site-hall': '遗址保护大厅' }
const currentHallName = computed(() => hallNames[currentHall.value] || currentHall.value)
const hasNextExhibit = computed(() => exhibitIndex.value < exhibits.value.length - 1)
const nextExhibit = computed(() => hasNextExhibit.value ? exhibits.value[exhibitIndex.value + 1] : null)

onMounted(async () => {
  loadingExhibits.value = true
  const result = await api.exhibits.list({ hall: currentHall.value, sort: 'display_order', is_active: 'true' })
  loadingExhibits.value = false
  if (result.ok) {
    exhibits.value = result.data.exhibits || result.data || []
  }
})

function onHallIntroDone() {
  if (exhibits.value.length > 0) {
    enterExhibit(exhibits.value[0])
    subStep.value = 'exhibit-chat'
    bufferEvent('hall_enter', { hall: currentHall.value })
  }
}

async function onNextExhibit() {
  if (hasNextExhibit.value) {
    const next = exhibits.value[exhibitIndex.value + 1]
    await enterExhibit(next)
    exhibitIndex.value++
    subStep.value = 'exhibit-chat'
  } else {
    await onHallComplete()
  }
}

async function onHallComplete() {
  await completeHall()
}

function onDeepDive() {
  bufferEvent('exhibit_deep_dive', { exhibit_id: currentExhibit.value?.id })
}
</script>

<template>
  <div class="exhibit-tour">
    <div class="tour-header-bar">
      <span class="hall-name">{{ currentHallName }}</span>
      <span class="exhibit-progress">{{ exhibitIndex + 1 }} / {{ exhibits.length }}</span>
    </div>
    <div v-if="loadingExhibits" class="loading">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      <span>加载展品中...</span>
    </div>
    <template v-else>
      <HallIntro v-if="subStep === 'hall-intro'" :hall="currentHall" :hall-name="currentHallName" @done="onHallIntroDone" />
      <template v-if="subStep === 'exhibit-chat'">
        <ExhibitChat :exhibit="currentExhibit" @deep-dive="onDeepDive" />
        <ExhibitNavigator :has-next="hasNextExhibit" :next-exhibit="nextExhibit" :is-last="exhibitIndex >= exhibits.length - 1" @next="onNextExhibit" @complete="onHallComplete" @deep-dive="onDeepDive" />
      </template>
    </template>
  </div>
</template>

<style scoped>
.exhibit-tour { display: flex; flex-direction: column; height: 100%; }
.tour-header-bar { display: flex; justify-content: space-between; align-items: center; padding: 12px 24px; background: rgba(255,255,255,0.03); border-bottom: 1px solid rgba(255,255,255,0.08); }
.hall-name { font-size: 16px; font-weight: 600; color: #d4a574; }
.exhibit-progress { font-size: 14px; color: rgba(255,255,255,0.5); }
.loading { display: flex; align-items: center; justify-content: center; gap: 12px; padding: 60px; color: rgba(255,255,255,0.5); }
</style>
