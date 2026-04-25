<template>
  <section class="museum-page">
    <div v-if="$slots.breadcrumb" class="museum-page-breadcrumb">
      <slot name="breadcrumb" />
    </div>

    <header v-if="$slots.hero" class="museum-page-hero">
      <slot name="hero" />
    </header>

    <div v-if="$slots.hero" class="museum-page-divider">
      <slot name="divider">
        <hr />
      </slot>
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
  gap: var(--space-4);
}

.museum-page-breadcrumb {
  font-size: var(--font-size-caption);
  color: var(--color-text-muted);
}

.museum-page-hero {
  color: var(--color-text-primary);
}

.museum-page-divider hr {
  border: 0;
  border-top: 1px solid var(--color-divider);
}

.museum-page-content {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--space-4);
}

@media (min-width: 1024px) {
  .museum-page-content {
    grid-template-columns: auto 1fr;
  }
}
</style>
