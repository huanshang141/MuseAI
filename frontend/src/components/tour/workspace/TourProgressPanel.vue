<script setup>
import { computed } from 'vue'
import { useTour } from '../../../composables/useTour.js'

const { tourSession, currentHall, hallExhibits, completeHall } = useTour()

const hallNames = { 'relic-hall': '出土文物展厅', 'site-hall': '遗址保护大厅' }

const visitedExhibitIds = computed(() => tourSession.value?.visited_exhibit_ids ?? [])

const exhibitProgress = computed(() => {
  const total = hallExhibits.value?.length ?? 0
  const visited = visitedExhibitIds.value.length
  return { visited, total, percent: total ? Math.round((visited / total) * 100) : 0 }
})

const currentHallName = computed(() => hallNames[currentHall.value] || currentHall.value || '-')
</script>

<template>
  <div class="tour-progress-panel">
    <div class="progress-section">
      <h4 class="progress-heading">展厅进度</h4>
      <div class="progress-info">
        <span class="progress-label">当前展厅</span>
        <span class="progress-value">{{ currentHallName }}</span>
      </div>
      <div class="progress-info">
        <span class="progress-label">展品进度</span>
        <span class="progress-value">{{ exhibitProgress.visited }}/{{ exhibitProgress.total }}</span>
      </div>
      <div class="progress-bar-track">
        <div class="progress-bar-fill" :style="{ width: exhibitProgress.percent + '%' }" />
      </div>
    </div>

    <div class="progress-section">
      <h4 class="progress-heading">已浏览展品</h4>
      <div class="visited-list">
        <div
          v-for="exhibit in hallExhibits?.filter(e => visitedExhibitIds.includes(e.id))"
          :key="exhibit.id"
          class="visited-item"
        >
          <span class="visited-check">✓</span>
          <span>{{ exhibit.name }}</span>
        </div>
        <div v-if="!visitedExhibitIds.length" class="empty-hint">
          尚未浏览展品
        </div>
      </div>
    </div>

    <div class="progress-section">
      <el-button
        data-testid="complete-hall-btn"
        type="primary"
        @click="completeHall"
      >
        完成当前展厅
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.tour-progress-panel {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.progress-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.progress-heading {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
}

.progress-label {
  color: var(--color-text-muted);
}

.progress-value {
  font-weight: 500;
  color: var(--color-text-primary);
}

.progress-bar-track {
  height: 6px;
  background: var(--color-bg-subtle);
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: var(--color-accent);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.visited-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.visited-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--color-text-primary);
}

.visited-check {
  color: var(--color-accent);
  font-weight: 600;
}

.empty-hint {
  color: var(--color-text-muted);
  font-size: 13px;
}
</style>
