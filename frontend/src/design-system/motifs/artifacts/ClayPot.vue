<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: { type: [Number, String], default: 24 },
  color: { type: String, default: 'currentColor' },
  strokeWidth: { type: [Number, String], default: 2 },
  variant: { type: String, default: 'outline' },
  ariaLabel: { type: String, default: 'Clay pot' },
})

const normalizedSize = computed(() => (typeof props.size === 'number' ? `${props.size}px` : props.size))
const showFilled = computed(() => props.variant === 'filled' || props.variant === 'both')
</script>

<template>
  <svg
    :width="normalizedSize"
    :height="normalizedSize"
    viewBox="0 0 100 120"
    role="img"
    :aria-label="ariaLabel"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M30 12 H70 V22 C70 22 84 30 84 54 C84 96 64 108 50 108 C36 108 16 96 16 54 C16 30 30 22 30 22 Z"
      :fill="showFilled ? color : 'none'"
      :stroke="color"
      :stroke-width="strokeWidth"
      :opacity="showFilled ? 0.2 : 1"
    />
  </svg>
</template>
