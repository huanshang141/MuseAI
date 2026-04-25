<script setup>
import { FishSwim } from '../motifs/index.js'

defineProps({
  ornament: { type: Boolean, default: false },
})
</script>

<template>
  <div class="section-divider">
    <div class="line" />
    <FishSwim v-if="ornament" :size="24" class="ornament" aria-label="Divider ornament" />
  </div>
</template>

<style scoped>
.section-divider {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
}

.line {
  flex: 1;
  height: 1px;
  background: var(--color-divider);
}

.ornament {
  color: var(--color-gold-line);
}
</style>
