<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: { type: [Number, String], default: 24 },
  color: { type: String, default: 'currentColor' },
  strokeWidth: { type: [Number, String], default: 1.5 },
  variant: { type: String, default: 'outline' },
  ariaLabel: { type: String, default: 'Net pattern' },
})

const normalizedSize = computed(() => (typeof props.size === 'number' ? `${props.size}px` : props.size))
</script>

<template>
  <svg
    :width="normalizedSize"
    :height="normalizedSize"
    viewBox="0 0 120 120"
    role="img"
    :aria-label="ariaLabel"
    xmlns="http://www.w3.org/2000/svg"
  >
    <g :stroke="color" :stroke-width="strokeWidth" fill="none" opacity="0.7">
      <path d="M0 20 H120" />
      <path d="M0 50 H120" />
      <path d="M0 80 H120" />
      <path d="M20 0 V120" />
      <path d="M50 0 V120" />
      <path d="M80 0 V120" />
      <path d="M0 0 L120 120" />
      <path d="M120 0 L0 120" />
    </g>
  </svg>
</template>
