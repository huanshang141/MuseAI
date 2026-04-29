<script setup>
import { computed } from 'vue'
import { onMounted } from 'vue'
import { useTour } from '../composables/useTour.js'
import OnboardingQuiz from '../components/tour/OnboardingQuiz.vue'
import OpeningNarrative from '../components/tour/OpeningNarrative.vue'
import HallSelect from '../components/tour/HallSelect.vue'
import TourWorkspace from '../components/tour/TourWorkspace.vue'
import TourReport from '../components/tour/TourReport.vue'

const { tourStep, restoreSession, setupBeforeUnload, resetTour } = useTour()

const isImmersiveStep = computed(() =>
  ['onboarding', 'opening', 'hall-select', 'report'].includes(tourStep.value)
)

onMounted(async () => {
  setupBeforeUnload()
  const restored = await restoreSession()
  if (!restored) {
    tourStep.value = 'onboarding'
  }
})
</script>

<template>
  <div class="tour-container" :class="{ 'tour-container--immersive': isImmersiveStep }">
    <div class="tour-content">
      <OnboardingQuiz v-if="tourStep === 'onboarding'" />
      <OpeningNarrative v-else-if="tourStep === 'opening'" />
      <HallSelect v-else-if="tourStep === 'hall-select'" />
      <TourWorkspace v-else-if="tourStep === 'tour'" />
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
  background: var(--color-bg-base, #f5eedc);
  color: var(--color-text-primary, #2a2420);
}

.tour-container--immersive {
  background: #1a1a2e;
  color: #e0e0e0;
}

.tour-content {
  flex: 1;
  overflow-y: auto;
}
</style>
