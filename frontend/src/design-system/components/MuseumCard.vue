<script setup>
defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
})
</script>

<template>
  <article class="museum-card">
    <header v-if="title || subtitle" class="museum-card-header">
      <h3 v-if="title" class="museum-card-title">{{ title }}</h3>
      <p v-if="subtitle" class="museum-card-subtitle">{{ subtitle }}</p>
    </header>
    <div class="museum-card-content">
      <slot />
    </div>
  </article>
</template>

<style scoped>
.museum-card {
  background: var(--color-bg-base);
  color: var(--color-text-primary);
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
}

.museum-card-header {
  padding: var(--space-4) var(--space-4) 0;
}

.museum-card-title {
  margin: 0;
  font-size: var(--font-size-h4);
  font-weight: var(--font-weight-semibold);
  font-family: var(--font-family-base);
}

.museum-card-subtitle {
  margin: var(--space-1) 0 0;
  font-size: var(--font-size-body-sm);
  color: var(--color-text-muted);
}

.museum-card-content {
  padding: var(--space-4);
}
</style>
