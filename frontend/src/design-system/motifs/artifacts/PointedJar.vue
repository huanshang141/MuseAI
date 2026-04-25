<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: { type: [Number, String], default: 24 },
  color: { type: String, default: 'currentColor' },
  strokeWidth: { type: [Number, String], default: 2 },
  variant: { type: String, default: 'outline' },
  ariaLabel: { type: String, default: 'Pointed jar' },
})

const normalizedSize = computed(() => (typeof props.size === 'number' ? `${props.size}px` : props.size))
const showFilled = computed(() => props.variant === 'filled' || props.variant === 'both')
</script>

<template>
  <svg
    :width="normalizedSize"
    :height="normalizedSize"
    viewBox="0 0 100 140"
    role="img"
    :aria-label="ariaLabel"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M35 10 H65 V30 C65 55 82 95 50 132 C18 95 35 55 35 30 Z"
      :fill="showFilled ? color : 'none'"
      :stroke="color"
      :stroke-width="strokeWidth"
      :opacity="showFilled ? 0.2 : 1"
    />
  </svg>
</template>
