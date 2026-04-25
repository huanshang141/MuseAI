<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: { type: [Number, String], default: 24 },
  color: { type: String, default: 'currentColor' },
  strokeWidth: { type: [Number, String], default: 1.5 },
  variant: { type: String, default: 'outline' },
  ariaLabel: { type: String, default: 'Triangle pattern' },
})

const normalizedSize = computed(() => (typeof props.size === 'number' ? `${props.size}px` : props.size))
const showFilled = computed(() => props.variant === 'filled' || props.variant === 'both')
</script>

<template>
  <svg
    :width="normalizedSize"
    :height="normalizedSize"
    viewBox="0 0 120 60"
    role="img"
    :aria-label="ariaLabel"
    xmlns="http://www.w3.org/2000/svg"
  >
    <g :stroke="color" :stroke-width="strokeWidth" :fill="showFilled ? color : 'none'" :opacity="showFilled ? 0.25 : 1">
      <path d="M10 50 L25 20 L40 50 Z" />
      <path d="M40 50 L55 20 L70 50 Z" />
      <path d="M70 50 L85 20 L100 50 Z" />
    </g>
  </svg>
</template>
