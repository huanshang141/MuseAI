<script setup>
const props = defineProps({
  path: {
    type: Array,
    default: () => [],
  },
  exhibits: {
    type: Array,
    default: () => [],
  },
  selectedExhibit: {
    type: Object,
    default: null,
  },
})

const emit = defineEmits(['select-exhibit'])
</script>

<template>
  <el-card class="floor-map">
    <template #header>
      <span>楼层导览图</span>
    </template>

    <div class="map-container">
      <!-- Placeholder for floor map visualization -->
      <div class="map-placeholder">
        <el-icon :size="60"><MapLocation /></el-icon>
        <p>楼层导览图</p>
        <p class="hint">点击展品标记查看详情</p>

        <!-- Show path stops if available -->
        <div v-if="path && path.length" class="path-indicator">
          <el-tag type="success">当前路线: {{ path.length }} 站</el-tag>
        </div>
      </div>

      <!-- Show exhibits list when no actual map -->
      <div v-if="exhibits && exhibits.length && !path?.length" class="exhibits-grid">
        <div
          v-for="exhibit in exhibits.slice(0, 9)"
          :key="exhibit.id"
          class="exhibit-marker"
          :class="{ selected: selectedExhibit?.id === exhibit.id }"
          @click="emit('select-exhibit', exhibit)"
        >
          <el-icon><Location /></el-icon>
          <span>{{ exhibit.name }}</span>
        </div>
      </div>
    </div>
  </el-card>
</template>

<script>
import { MapLocation, Location } from '@element-plus/icons-vue'

export default {
  components: { MapLocation, Location },
}
</script>

<style scoped>
.floor-map {
  height: 100%;
  min-height: 400px;
}

.map-container {
  height: 100%;
  min-height: 350px;
  display: flex;
  flex-direction: column;
}

.map-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  color: var(--el-text-color-secondary);
}

.map-placeholder p {
  margin: 8px 0;
}

.map-placeholder .hint {
  font-size: 12px;
  opacity: 0.7;
}

.path-indicator {
  margin-top: 16px;
}

.exhibits-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  padding: 16px;
}

.exhibit-marker {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
}

.exhibit-marker:hover {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.exhibit-marker.selected {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-8);
}

.exhibit-marker span {
  font-size: 12px;
  margin-top: 4px;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
</style>
