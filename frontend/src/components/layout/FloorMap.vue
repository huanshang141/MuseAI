<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  exhibits: Array,
  path: Array,
  selectedExhibit: Object
})

const emit = defineEmits(['select-exhibit'])

const currentFloor = ref(1)
const scale = ref(1)

// Map dimensions (in SVG units)
const MAP_WIDTH = 800
const MAP_HEIGHT = 600

const filteredExhibits = computed(() => {
  const all = props.exhibits || props.path || []
  return all.filter(e => (e.floor || e.location?.floor || 1) === currentFloor.value)
})

const pathData = computed(() => {
  if (!props.path || props.path.length < 2) return ''

  const points = props.path
    .filter(e => (e.floor || e.location?.floor || 1) === currentFloor.value)
    .map(e => {
      const x = e.location?.x || e.x || 0
      const y = e.location?.y || e.y || 0
      return `${x * scale.value},${y * scale.value}`
    })

  if (points.length < 2) return ''
  return `M ${points.join(' L ')}`
})

function getExhibitPosition(exhibit) {
  const x = exhibit.location?.x || exhibit.x || 0
  const y = exhibit.location?.y || exhibit.y || 0
  return {
    x: x * scale.value,
    y: y * scale.value
  }
}

function isSelected(exhibit) {
  return props.selectedExhibit?.id === exhibit.id
}

function isInPath(exhibit) {
  return props.path?.some(e => e.id === exhibit.id)
}
</script>

<template>
  <el-card class="floor-map-card">
    <template #header>
      <div class="map-header">
        <span>展厅地图</span>
        <div class="map-controls">
          <el-radio-group v-model="currentFloor" size="small">
            <el-radio-button :label="1">一楼</el-radio-button>
            <el-radio-button :label="2">二楼</el-radio-button>
            <el-radio-button :label="3">三楼</el-radio-button>
          </el-radio-group>
          <el-slider v-model="scale" :min="0.5" :max="2" :step="0.1" style="width: 100px; margin-left: 16px;" />
        </div>
      </div>
    </template>

    <div class="map-container">
      <svg
        :viewBox="`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`"
        class="floor-map"
      >
        <!-- Background -->
        <rect width="100%" height="100%" fill="#f5f7fa" />

        <!-- Grid lines -->
        <g stroke="#e4e7ed" stroke-width="1">
          <line v-for="i in 9" :key="`h${i}`" x1="0" :y1="i * 60" x2="800" :y2="i * 60" />
          <line v-for="i in 13" :key="`v${i}`" :x1="i * 60" y1="0" :x2="i * 60" y2="600" />
        </g>

        <!-- Path line -->
        <path
          v-if="pathData"
          :d="pathData"
          fill="none"
          stroke="#409eff"
          stroke-width="3"
          stroke-dasharray="5,5"
        />

        <!-- Exhibits -->
        <g
          v-for="exhibit in filteredExhibits"
          :key="exhibit.id"
          class="exhibit-marker"
          :class="{
            'is-selected': isSelected(exhibit),
            'in-path': isInPath(exhibit)
          }"
          @click="emit('select-exhibit', exhibit)"
        >
          <circle
            :cx="getExhibitPosition(exhibit).x"
            :cy="getExhibitPosition(exhibit).y"
            r="12"
            :fill="isSelected(exhibit) ? '#f56c6c' : isInPath(exhibit) ? '#409eff' : '#67c23a'"
            stroke="#fff"
            stroke-width="2"
            class="marker-circle"
          />
          <text
            :x="getExhibitPosition(exhibit).x"
            :y="getExhibitPosition(exhibit).y + 25"
            text-anchor="middle"
            font-size="12"
            fill="#606266"
          >
            {{ exhibit.name }}
          </text>
        </g>
      </svg>
    </div>

    <div class="map-legend">
      <div class="legend-item">
        <span class="legend-dot" style="background: #67c23a;"></span>
        <span>普通展品</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot" style="background: #409eff;"></span>
        <span>路线中的展品</span>
      </div>
      <div class="legend-item">
        <span class="legend-dot" style="background: #f56c6c;"></span>
        <span>当前选中</span>
      </div>
    </div>
  </el-card>
</template>

<style scoped>
.floor-map-card {
  height: 100%;
}

.map-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.map-controls {
  display: flex;
  align-items: center;
}

.map-container {
  height: 500px;
  overflow: auto;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
}

.floor-map {
  width: 100%;
  height: 100%;
}

.exhibit-marker {
  cursor: pointer;
}

.marker-circle {
  transition: all 0.2s;
}

.exhibit-marker:hover .marker-circle {
  r: 15;
}

.map-legend {
  display: flex;
  gap: 20px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e4e7ed;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #606266;
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}
</style>
