<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '' },
  width: { type: [String, Number], default: '520px' },
  mobileFullscreen: { type: Boolean, default: true },
})

const emit = defineEmits(['update:visible'])

const isMobile = ref(false)
let mediaQuery

const syncIsMobile = () => {
  isMobile.value = !!mediaQuery?.matches
}

const dialogVisible = computed({
  get: () => props.visible,
  set: (value) => emit('update:visible', value),
})

const fullscreen = computed(() => props.mobileFullscreen && isMobile.value)

onMounted(() => {
  mediaQuery = window.matchMedia('(max-width: 767px)')
  syncIsMobile()
  mediaQuery.addEventListener('change', syncIsMobile)
})

onUnmounted(() => {
  mediaQuery?.removeEventListener('change', syncIsMobile)
})
</script>

<template>
  <el-dialog
    v-model="dialogVisible"
    :title="title"
    :width="width"
    :fullscreen="fullscreen"
    class="museum-dialog"
    v-bind="$attrs"
  >
    <div class="museum-dialog-body">
      <slot />
    </div>

    <template v-if="$slots.footer" #footer>
      <div class="museum-dialog-footer">
        <slot name="footer" />
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.museum-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid var(--color-divider);
  margin: 0;
  padding: var(--space-4) var(--space-6);
}

.museum-dialog :deep(.el-dialog__title) {
  font-family: var(--font-family-base);
  font-size: var(--font-size-h3);
  font-weight: var(--font-weight-semibold);
}

.museum-dialog :deep(.el-dialog__body) {
  padding: 0;
}

.museum-dialog :deep(.el-dialog) {
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
}

.museum-dialog-body {
  padding: var(--space-6);
}

.museum-dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}
</style>
