<script setup>
defineProps({
  activeTab: { type: String, required: true },
})

defineEmits(['update:activeTab'])
</script>

<template>
  <div class="tour-secondary-tabs" data-testid="tour-secondary-tabs">
    <button
      v-for="tab in [
        { key: 'session', label: '导览会话' },
        { key: 'exhibit', label: '展品速览' },
        { key: 'progress', label: '导览进度' },
        { key: 'settings', label: '导览设置' },
      ]"
      :key="tab.key"
      class="tab-btn"
      :class="{ active: activeTab === tab.key }"
      @click="$emit('update:activeTab', tab.key)"
    >
      {{ tab.label }}
    </button>
  </div>
</template>

<style scoped>
.tour-secondary-tabs {
  display: flex;
  gap: 4px;
  padding: 8px 16px;
  border-bottom: 1px solid var(--color-border);
  overflow-x: auto;
}

.tab-btn {
  padding: 6px 16px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  font-size: 14px;
  cursor: pointer;
  border-radius: 6px;
  white-space: nowrap;
  transition: background 0.15s, color 0.15s;
}

.tab-btn:hover {
  background: var(--color-bg-subtle);
}

.tab-btn.active {
  background: var(--color-accent);
  color: var(--color-text-inverse);
}
</style>
