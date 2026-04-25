<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: { type: [Number, String], default: 24 },
  color: { type: String, default: 'currentColor' },
  strokeWidth: { type: [Number, String], default: 2 },
  variant: { type: String, default: 'outline' },
  ariaLabel: { type: String, default: 'Fish swim symbol' },
})

const normalizedSize = computed(() => (typeof props.size === 'number' ? `${props.size}px` : props.size))
const showOutline = computed(() => props.variant === 'outline' || props.variant === 'both')
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
    <path
      d="M15 30 C30 10, 70 10, 90 30 C70 50, 30 50, 15 30 Z"
      :fill="showFilled ? color : 'none'"
      :stroke="showOutline ? color : 'none'"
      :stroke-width="strokeWidth"
      :opacity="showFilled ? 0.25 : 1"
    />
    <path
      d="M90 30 L110 15 L108 30 L110 45 Z"
      :fill="showFilled ? color : 'none'"
      :stroke="showOutline ? color : 'none'"
      :stroke-width="strokeWidth"
      :opacity="showFilled ? 0.25 : 1"
    />
    <circle cx="38" cy="26" r="3" :fill="color" />
  </svg>
</template>
