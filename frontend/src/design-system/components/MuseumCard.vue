<script setup>
import { computed } from 'vue'
import { ClayPot, FishFaceBasin, PointedJar } from '../motifs/index.js'

const props = defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  accent: { type: Boolean, default: false },
  motif: { type: String, default: '' },
  variant: {
    type: String,
    default: 'elevated',
    validator: (value) => ['flat', 'outlined', 'elevated'].includes(value),
  },
})

const motifComponent = computed(() => {
  if (props.motif === 'jar') return PointedJar
  if (props.motif === 'basin') return FishFaceBasin
  if (props.motif === 'pot') return ClayPot
  return null
})
</script>

<template>
  <article class="museum-card" :class="`is-${variant}`">
    <div v-if="accent" class="museum-card-accent" />
    <header v-if="title || subtitle" class="museum-card-header">
      <div>
        <h3 v-if="title" class="museum-card-title">{{ title }}</h3>
        <p v-if="subtitle" class="museum-card-subtitle">{{ subtitle }}</p>
      </div>
      <component :is="motifComponent" v-if="motifComponent" :size="24" class="museum-card-motif" />
    </header>
    <div class="museum-card-content">
      <slot />
    </div>
  </article>
</template>

<style scoped>
.museum-card {
  background: var(--color-bg-elevated);
  color: var(--color-text-primary);
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
}

.museum-card.is-elevated {
  box-shadow: var(--shadow-md);
}

.museum-card.is-flat {
  border-color: transparent;
  box-shadow: var(--shadow-none);
}

.museum-card-accent {
  height: 2px;
  background: var(--color-gold-line);
}

.museum-card-header {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
  align-items: center;
  padding: var(--space-4) var(--space-4) 0;
}

.museum-card-title {
  margin: 0;
  font-size: var(--font-size-h4);
  font-family: var(--font-family-display);
}

.museum-card-subtitle {
  margin: var(--space-1) 0 0;
  font-size: var(--font-size-body-sm);
  color: var(--color-text-secondary);
}

.museum-card-content {
  padding: var(--space-4);
}

.museum-card-motif {
  color: var(--color-accent);
}
</style>
