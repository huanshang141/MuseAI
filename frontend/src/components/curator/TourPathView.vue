<script setup>
defineProps({
  path: Object
})

const emit = defineEmits(['select-exhibit'])

function getImportanceType(importance) {
  if (importance >= 5) return 'danger'
  if (importance >= 4) return 'warning'
  return 'info'
}
</script>

<template>
  <el-card v-if="path">
    <template #header>
      <div class="path-header">
        <span>推荐路线</span>
        <el-tag type="success">
          {{ path.exhibit_count }} 个展品 · {{ path.estimated_duration }} 分钟
        </el-tag>
      </div>
    </template>

    <el-timeline>
      <el-timeline-item
        v-for="(exhibit, index) in path.path"
        :key="exhibit.id"
        :type="index === 0 ? 'primary' : ''"
        :hollow="index > 0"
      >
        <div
          class="exhibit-item"
          @click="emit('select-exhibit', exhibit)"
        >
          <div class="exhibit-header">
            <span class="exhibit-name">{{ index + 1 }}. {{ exhibit.name }}</span>
            <el-tag :type="getImportanceType(exhibit.importance)" size="small">
              {{ exhibit.category }}
            </el-tag>
          </div>
          <div class="exhibit-meta">
            <span>展厅: {{ exhibit.hall }}</span>
            <span>参观时间: {{ exhibit.estimated_time }} 分钟</span>
          </div>
        </div>
      </el-timeline-item>
    </el-timeline>
  </el-card>
</template>

<style scoped>
.path-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.exhibit-item {
  cursor: pointer;
  padding: 8px;
  border-radius: 4px;
  transition: background 0.2s;
}

.exhibit-item:hover {
  background: var(--el-fill-color-light);
}

.exhibit-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.exhibit-name {
  font-weight: 500;
}

.exhibit-meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  display: flex;
  gap: 12px;
}
</style>
