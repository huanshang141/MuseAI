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
  setupBeforeUnload()
  const restored = await restoreSession()
  if (!restored) {
    tourStep.value = 'onboarding'
  }
})
</script>

<template>
  <div class="tour-container">
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
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #1a1a2e;
  color: #e0e0e0;
}

.tour-content {
  flex: 1;
  overflow-y: auto;
}
</style>
