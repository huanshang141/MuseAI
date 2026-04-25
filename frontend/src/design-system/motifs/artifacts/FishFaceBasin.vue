<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: { type: [Number, String], default: 24 },
  color: { type: String, default: 'currentColor' },
  strokeWidth: { type: [Number, String], default: 2 },
  variant: { type: String, default: 'outline' },
  ariaLabel: { type: String, default: 'Fish face basin' },
})

const normalizedSize = computed(() => (typeof props.size === 'number' ? `${props.size}px` : props.size))
const showFilled = computed(() => props.variant === 'filled' || props.variant === 'both')
</script>

<template>
  <svg
    :width="normalizedSize"
    :height="normalizedSize"
    viewBox="0 0 120 80"
    role="img"
    :aria-label="ariaLabel"
    xmlns="http://www.w3.org/2000/svg"
  >
    <ellipse
      cx="60"
      cy="40"
      rx="52"
      ry="30"
      :fill="showFilled ? color : 'none'"
      :stroke="color"
      :stroke-width="strokeWidth"
      :opacity="showFilled ? 0.2 : 1"
    />
    <circle cx="48" cy="36" r="3" :fill="color" />
    <circle cx="72" cy="36" r="3" :fill="color" />
    <path d="M48 50 Q60 58 72 50" fill="none" :stroke="color" :stroke-width="strokeWidth" />
  </svg>
</template>
