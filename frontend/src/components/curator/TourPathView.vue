<script setup>
const props = defineProps({
  path: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['select-exhibit'])
</script>

<template>
  <el-card v-if="path" class="tour-path-view">
    <template #header>
      <div class="path-header">
        <span>推荐路线</span>
        <el-tag size="small">约 {{ path.estimated_time || 60 }} 分钟</el-tag>
      </div>
    </template>

    <el-timeline>
      <el-timeline-item
        v-for="(exhibit, index) in path.path || path.exhibits || []"
        :key="exhibit.id || index"
        :timestamp="exhibit.location || `第 ${index + 1} 站`"
        placement="top"
      >
        <el-card
          shadow="hover"
          class="exhibit-card"
          @click="emit('select-exhibit', exhibit)"
        >
          <div class="exhibit-name">{{ exhibit.name }}</div>
          <div class="exhibit-category" v-if="exhibit.category">
            {{ exhibit.category }}
          </div>
        </el-card>
      </el-timeline-item>
    </el-timeline>
  </el-card>
</template>

<style scoped>
.tour-path-view {
  max-height: 400px;
  overflow-y: auto;
}

.path-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.exhibit-card {
  cursor: pointer;
  transition: all 0.3s;
}

.exhibit-card:hover {
  border-color: var(--el-color-primary);
}

.exhibit-name {
  font-weight: 500;
}

.exhibit-category {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
</style>
