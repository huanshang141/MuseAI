<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useTour } from '../composables/useTour.js'
import OnboardingQuiz from '../components/tour/OnboardingQuiz.vue'
import OpeningNarrative from '../components/tour/OpeningNarrative.vue'
import HallSelect from '../components/tour/HallSelect.vue'
import ExhibitTour from '../components/tour/ExhibitTour.vue'
import TourReport from '../components/tour/TourReport.vue'

const { tourStep, restoreSession, setupBeforeUnload, resetTour } = useTour()

onMounted(async () => {
  document.body.classList.add('tour-mode')
  setupBeforeUnload()
  const restored = await restoreSession()
  if (!restored) {
    tourStep.value = 'onboarding'
  }
})

onUnmounted(() => {
  document.body.classList.remove('tour-mode')
})
</script>

<template>
  <div class="tour-container">
    <div v-if="tourStep !== 'onboarding' && tourStep !== 'report'" class="tour-header">
      <div class="tour-header-left">
        <span class="tour-logo">🏛️ 半坡AI导览</span>
      </div>
      <div class="tour-header-right">
        <el-button text @click="resetTour">退出导览</el-button>
      </div>
    </div>

    <div class="tour-content">
      <OnboardingQuiz v-if="tourStep === 'onboarding'" />
      <OpeningNarrative v-else-if="tourStep === 'opening'" />
      <HallSelect v-else-if="tourStep === 'hall-select'" />
      <ExhibitTour v-else-if="tourStep === 'tour'" />
      <TourReport v-else-if="tourStep === 'report'" />
    </div>
  </div>
</template>

<style scoped>
.tour-container {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #1a1a2e;
  color: #e0e0e0;
  overflow: hidden;
}

.tour-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 24px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.tour-logo {
  font-size: 18px;
  font-weight: 600;
}

.tour-content {
  flex: 1;
  overflow-y: auto;
}
</style>

<style>
body.tour-mode .app-header,
body.tour-mode .app-sidebar {
  display: none !important;
}
body.tour-mode .app-main {
  margin: 0 !important;
  padding: 0 !important;
}
</style>
