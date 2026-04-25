<script setup>
import { computed } from 'vue'
import { FishFaceBasin, FishSwim, PointedJar } from '../motifs/index.js'

const props = defineProps({
  icon: {
    type: String,
    default: 'jar',
    validator: (value) => ['jar', 'basin', 'fish'].includes(value),
  },
  title: { type: String, default: '' },
  description: { type: String, default: '' },
})

const iconComponent = computed(() => {
  if (props.icon === 'basin') return FishFaceBasin
  if (props.icon === 'fish') return FishSwim
  return PointedJar
})
</script>

<template>
  <div class="empty-state">
    <component :is="iconComponent" :size="72" class="empty-icon" />
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
  color: var(--color-text-secondary);
}

.empty-icon {
  color: var(--color-accent);
}

.empty-title {
  margin: 0;
  font-size: var(--font-size-h3);
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
