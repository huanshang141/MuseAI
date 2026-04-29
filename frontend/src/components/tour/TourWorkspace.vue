<script setup>
import { useTourWorkbench } from '../../composables/useTourWorkbench.js'
import TourWorkspaceSidebar from './workspace/TourWorkspaceSidebar.vue'
import TourSecondaryTabs from './workspace/TourSecondaryTabs.vue'
import TourSessionPanel from './workspace/TourSessionPanel.vue'
import TourExhibitQuickView from './workspace/TourExhibitQuickView.vue'
import TourProgressPanel from './workspace/TourProgressPanel.vue'
import TourSettingsPanel from './workspace/TourSettingsPanel.vue'

const { activeTab } = useTourWorkbench()

function onSwitchTab(tab) {
  activeTab.value = tab
}
</script>

<template>
  <section class="tour-workspace" data-testid="tour-workspace">
    <TourWorkspaceSidebar @switch-tab="onSwitchTab" />
    <div class="tour-workspace-main">
      <TourSecondaryTabs :active-tab="activeTab" @update:active-tab="onSwitchTab" />
      <div class="tour-workspace-panel">
        <TourSessionPanel v-if="activeTab === 'session'" />
        <TourExhibitQuickView v-else-if="activeTab === 'exhibit'" @switch-tab="onSwitchTab" />
        <TourProgressPanel v-else-if="activeTab === 'progress'" />
        <TourSettingsPanel v-else-if="activeTab === 'settings'" />
      </div>
    </div>
  </section>
</template>

<style scoped>
.tour-workspace {
  width: 100%;
  height: 100%;
  display: flex;
  background: var(--color-bg-base, #f5eedc);
  color: var(--color-text-primary, #2a2420);
}

.tour-workspace-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.tour-workspace-panel {
  flex: 1;
  overflow-y: auto;
}
</style>
