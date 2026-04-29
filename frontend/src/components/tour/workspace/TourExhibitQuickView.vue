<script setup>
import { useTour } from '../../../composables/useTour.js'
import { useTourWorkbench } from '../../../composables/useTourWorkbench.js'

const { hallExhibits, currentExhibit, enterExhibit } = useTour()
const { insertTemplateForExhibit, activeTab } = useTourWorkbench()

const emit = defineEmits(['switch-tab'])

const templates = [
  { key: 'intro', label: '介绍' },
  { key: 'controversy', label: '争议' },
  { key: 'relation', label: '关联' },
]

function onTemplateClick(exhibit, templateKey) {
  const ok = insertTemplateForExhibit(exhibit, templateKey)
  if (ok) {
    emit('switch-tab', 'session')
  }
}

function isCurrentExhibit(exhibit) {
  return currentExhibit.value?.id === exhibit.id
}
</script>

<template>
  <div class="tour-exhibit-quick-view">
    <div class="exhibit-list">
      <div
        v-for="exhibit in hallExhibits"
        :key="exhibit.id"
        class="exhibit-card"
        :class="{ current: isCurrentExhibit(exhibit) }"
      >
        <div class="exhibit-card-header">
          <span class="exhibit-card-name">{{ exhibit.name }}</span>
          <span v-if="exhibit.category" class="exhibit-card-category">{{ exhibit.category }}</span>
        </div>
        <div class="exhibit-card-templates">
          <button
            v-for="tpl in templates"
            :key="tpl.key"
            class="template-btn"
            @click="onTemplateClick(exhibit, tpl.key)"
          >
            {{ tpl.label }}
          </button>
        </div>
      </div>
    </div>
    <div v-if="!hallExhibits?.length" class="empty-hint">
      当前展厅暂无展品
    </div>
  </div>
</template>

<style scoped>
.tour-exhibit-quick-view {
  padding: 16px;
}

.exhibit-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.exhibit-card {
  padding: 12px 16px;
  border: 1px solid var(--color-border, #d9c9a8);
  border-radius: 8px;
  background: var(--color-bg-elevated, #fdfaf2);
  transition: border-color 0.15s;
}

.exhibit-card.current {
  border-color: var(--color-accent, #a94c2c);
  box-shadow: 0 0 0 1px var(--color-accent, #a94c2c);
}

.exhibit-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.exhibit-card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary, #2a2420);
}

.exhibit-card-category {
  font-size: 12px;
  color: var(--color-text-muted, #8a8074);
  background: var(--color-bg-subtle, #efe5cc);
  padding: 2px 8px;
  border-radius: 4px;
}

.exhibit-card-templates {
  display: flex;
  gap: 8px;
}

.template-btn {
  padding: 4px 12px;
  border: 1px solid var(--color-accent-soft, #c47a52);
  background: transparent;
  color: var(--color-accent, #a94c2c);
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}

.template-btn:hover {
  background: var(--color-accent, #a94c2c);
  color: var(--color-text-inverse, #f5eedc);
}

.empty-hint {
  text-align: center;
  padding: 32px 16px;
  color: var(--color-text-muted, #8a8074);
  font-size: 14px;
}
</style>
