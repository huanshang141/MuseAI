<script setup>
defineProps({
  variant: {
    type: String,
    default: 'primary',
    validator: (value) => ['primary', 'secondary', 'text'].includes(value),
  },
  size: {
    type: String,
    default: 'md',
    validator: (value) => ['sm', 'md', 'lg'].includes(value),
  },
  fullWidth: { type: Boolean, default: false },
})
</script>

<template>
  <el-button
    class="museum-button"
    :class="[`is-${variant}`, `is-${size}`, { 'is-full': fullWidth }]"
    v-bind="$attrs"
  >
    <slot />
  </el-button>
</template>

<style scoped>
.museum-button {
  border-radius: var(--radius-sm);
}

.museum-button.is-full {
  width: 100%;
}

.museum-button.is-primary {
  --el-button-bg-color: var(--color-accent);
  --el-button-border-color: var(--color-accent);
  --el-button-text-color: var(--color-text-inverse);
  --el-button-hover-bg-color: var(--color-accent-hover);
  --el-button-hover-border-color: var(--color-accent-hover);
  --el-button-hover-text-color: var(--color-text-inverse);
}

.museum-button.is-secondary {
  --el-button-bg-color: transparent;
  --el-button-border-color: var(--color-border);
  --el-button-text-color: var(--color-accent);
  --el-button-hover-bg-color: var(--color-bg-subtle);
  --el-button-hover-border-color: var(--color-accent);
  --el-button-hover-text-color: var(--color-accent);
}

.museum-button.is-text {
  --el-button-bg-color: transparent;
  --el-button-border-color: transparent;
  --el-button-text-color: var(--color-accent);
  --el-button-hover-bg-color: transparent;
  --el-button-hover-border-color: transparent;
  --el-button-hover-text-color: var(--color-accent-hover);
}

.museum-button.is-sm {
  --el-button-padding-horizontal: var(--space-3);
}

.museum-button.is-lg {
  --el-button-padding-horizontal: var(--space-6);
}
</style>
