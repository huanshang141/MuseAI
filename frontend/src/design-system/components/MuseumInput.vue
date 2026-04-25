<template>
  <el-input class="museum-input" v-bind="$attrs">
    <template v-for="(_, slotName) in $slots" #[slotName]="slotProps">
      <slot :name="slotName" v-bind="slotProps" />
    </template>
  </el-input>
</template>

<style scoped>
.museum-input :deep(.el-input__wrapper) {
  border-radius: var(--radius-sm);
  box-shadow: inset 0 0 0 1px var(--color-border);
}

.museum-input :deep(.el-input__wrapper.is-focus) {
  box-shadow: inset 0 0 0 1px var(--color-accent);
}
</style>
