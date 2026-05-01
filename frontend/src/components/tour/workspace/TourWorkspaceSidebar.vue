<script setup>
import { useTour } from '../../../composables/useTour.js'
import { useTourWorkbench } from '../../../composables/useTourWorkbench.js'

const { currentHall, currentExhibit, exhibitIndex, personaLabel } = useTour()
const { activeTab } = useTourWorkbench()

const hallNames = { 'relic-hall': '出土文物展厅', 'site-hall': '遗址保护大厅' }

defineEmits(['switch-tab'])
</script>

<template>
  <aside class="tour-workspace-sidebar" data-testid="tour-workspace-sidebar">
    <div class="sidebar-section">
      <h4 class="sidebar-heading">快捷入口</h4>
      <button
        v-for="tab in [
          { key: 'session', label: '导览会话' },
          { key: 'exhibit', label: '展品速览' },
          { key: 'progress', label: '导览进度' },
          { key: 'settings', label: '导览设置' },
        ]"
        :key="tab.key"
        class="sidebar-tab-btn"
        :class="{ active: activeTab === tab.key }"
        @click="$emit('switch-tab', tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <div class="sidebar-section">
      <h4 class="sidebar-heading">当前信息</h4>
      <div class="sidebar-info">
        <div class="info-item">
          <span class="info-label">展厅</span>
          <span class="info-value">{{ hallNames[currentHall] || currentHall || '-' }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">展品</span>
          <span class="info-value">{{ currentExhibit?.name || '-' }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">人设</span>
          <span class="info-value">{{ personaLabel || '-' }}</span>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.tour-workspace-sidebar {
  width: 240px;
  min-width: 240px;
  border-right: 1px solid var(--color-border);
  background: var(--color-bg-subtle);
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 12px;
  overflow-y: auto;
}

.sidebar-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sidebar-heading {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}

.sidebar-tab-btn {
  padding: 8px 12px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 14px;
  cursor: pointer;
  border-radius: 6px;
  text-align: left;
  transition: background 0.15s;
}

.sidebar-tab-btn:hover {
  background: rgba(169, 76, 44, 0.08);
}

.sidebar-tab-btn.active {
  background: var(--color-accent);
  color: var(--color-text-inverse);
}

.sidebar-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.info-label {
  color: var(--color-text-muted);
}

.info-value {
  color: var(--color-text-primary);
  font-weight: 500;
}
</style>
