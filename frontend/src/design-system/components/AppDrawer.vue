<script setup>
const props = defineProps({
  open: { type: Boolean, default: false },
  title: { type: String, default: '' },
})

const emit = defineEmits(['update:open'])
</script>

<template>
  <el-drawer
    :model-value="open"
    :title="title"
    direction="ltr"
    size="280px"
    class="app-drawer"
    @update:model-value="(value) => emit('update:open', value)"
  >
    <slot />
  </el-drawer>
</template>

<style scoped>
.app-drawer :deep(.el-drawer__body) {
  padding: 0;
  background: var(--color-bg-subtle);
}
</style>
