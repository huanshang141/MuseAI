<script setup>
import { computed } from 'vue'

const props = defineProps({
  size: { type: [Number, String], default: 24 },
  color: { type: String, default: 'currentColor' },
  strokeWidth: { type: [Number, String], default: 2 },
  variant: { type: String, default: 'outline' },
  ariaLabel: { type: String, default: 'Fish face symbol' },
})

const normalizedSize = computed(() => (typeof props.size === 'number' ? `${props.size}px` : props.size))
const showOutline = computed(() => props.variant === 'outline' || props.variant === 'both')
const showFilled = computed(() => props.variant === 'filled' || props.variant === 'both')
</script>

<template>
  <svg
    :width="normalizedSize"
    :height="normalizedSize"
    viewBox="0 0 100 100"
    role="img"
    :aria-label="ariaLabel"
    xmlns="http://www.w3.org/2000/svg"
  >
    <circle
      v-if="showFilled"
      cx="50"
      cy="50"
      r="44"
      :fill="color"
      opacity="0.15"
    />
    <circle
      v-if="showOutline"
      cx="50"
      cy="50"
      r="44"
      fill="none"
      :stroke="color"
      :stroke-width="strokeWidth"
    />
    <path
      d="M20 50 C35 30, 65 30, 80 50 C65 70, 35 70, 20 50 Z"
      :fill="showFilled ? color : 'none'"
      :stroke="color"
      :stroke-width="strokeWidth"
      :opacity="showFilled ? 0.3 : 1"
    />
    <circle cx="40" cy="47" r="3" :fill="color" />
    <circle cx="60" cy="47" r="3" :fill="color" />
    <path d="M40 60 Q50 68 60 60" fill="none" :stroke="color" :stroke-width="strokeWidth" />
  </svg>
</template>
