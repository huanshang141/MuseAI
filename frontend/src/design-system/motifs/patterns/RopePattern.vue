<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: { type: [Number, String], default: 24 },
  color: { type: String, default: 'currentColor' },
  strokeWidth: { type: [Number, String], default: 2 },
  variant: { type: String, default: 'outline' },
  ariaLabel: { type: String, default: 'Rope pattern' },
})

const normalizedSize = computed(() => (typeof props.size === 'number' ? `${props.size}px` : props.size))
</script>

<template>
  <svg
    :width="normalizedSize"
    :height="normalizedSize"
    viewBox="0 0 120 24"
    role="img"
    :aria-label="ariaLabel"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path d="M0 12 Q10 2 20 12 T40 12 T60 12 T80 12 T100 12 T120 12" fill="none" :stroke="color" :stroke-width="strokeWidth" />
    <path d="M0 12 Q10 22 20 12 T40 12 T60 12 T80 12 T100 12 T120 12" fill="none" :stroke="color" :stroke-width="strokeWidth" opacity="0.6" />
  </svg>
</template>
