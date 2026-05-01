<template>
  <section class="museum-page">
    <div v-if="$slots.breadcrumb" class="museum-page-breadcrumb">
      <slot name="breadcrumb" />
    </div>

    <div class="museum-page-content">
      <aside v-if="$slots.sidebar" class="museum-page-sidebar">
        <slot name="sidebar" />
      </aside>
      <div class="museum-page-main">
        <slot />
      </div>
    </div>
  </section>
</template>

<style scoped>
.museum-page {
  display: flex;
  flex-direction: column;
  gap: var(--space-fluid-md);
}

.museum-page-breadcrumb {
  font-size: var(--font-size-caption);
  color: var(--color-text-muted);
}

.museum-page-content {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-fluid-md);
}

@media (min-width: 1024px) {
  .museum-page-content {
    grid-template-columns: auto 1fr;
  }
}
</style>
