<script setup>
import { Box } from '@element-plus/icons-vue'

defineProps({
  title: { type: String, default: '' },
  description: { type: String, default: '' },
})
</script>

<template>
  <div class="empty-state">
    <el-icon :size="48" class="empty-icon"><Box /></el-icon>
    <h3 v-if="title" class="empty-title">{{ title }}</h3>
    <p v-if="description" class="empty-description">{{ description }}</p>
    <div v-if="$slots.default" class="empty-actions">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-8);
  text-align: center;
  color: var(--color-text-muted);
}

.empty-icon {
  color: var(--color-text-faint);
}

.empty-title {
  margin: 0;
  font-size: var(--font-size-h4);
  color: var(--color-text-primary);
}

.empty-description {
  margin: 0;
  font-size: var(--font-size-body);
}

.empty-actions {
  margin-top: var(--space-2);
}
</style>
