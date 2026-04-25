<script setup>
import { computed, ref } from 'vue'
import { MuseumCard } from '../../design-system/components/index.js'

const props = defineProps({
  exhibits: Array,
  path: Array,
  selectedExhibit: Object,
})

const emit = defineEmits(['select-exhibit'])

const currentFloor = ref(1)
const scale = ref(1)

const MAP_WIDTH = 800
const MAP_HEIGHT = 600

const filteredExhibits = computed(() => {
  const all = props.exhibits || props.path || []
  return all.filter((item) => (item.floor || item.location?.floor || 1) === currentFloor.value)
})

const pathData = computed(() => {
  if (!props.path || props.path.length < 2) return ''

  const points = props.path
    .filter((item) => (item.floor || item.location?.floor || 1) === currentFloor.value)
    .map((item) => {
      const x = item.location?.x || item.x || 0
      const y = item.location?.y || item.y || 0
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
    y: y * scale.value,
  }
}

function isSelected(exhibit) {
  return props.selectedExhibit?.id === exhibit.id
}

function isInPath(exhibit) {
  return props.path?.some((item) => item.id === exhibit.id)
}
</script>

<template>
  <MuseumCard title="展厅地图" subtitle="在图上点击展品可查看详情" motif="basin" class="floor-map-card">
    <template #default>
      <div class="map-controls">
        <el-radio-group v-model="currentFloor" size="small">
          <el-radio-button :label="1">一楼</el-radio-button>
          <el-radio-button :label="2">二楼</el-radio-button>
          <el-radio-button :label="3">三楼</el-radio-button>
        </el-radio-group>

        <el-slider v-model="scale" :min="0.5" :max="2" :step="0.1" class="map-zoom" />
      </div>

      <div class="map-container">
        <svg :viewBox="`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`" class="floor-map">
          <rect width="100%" height="100%" fill="#f5f7fa" />

          <g stroke="#e4e7ed" stroke-width="1">
            <line v-for="i in 9" :key="`h${i}`" x1="0" :y1="i * 60" x2="800" :y2="i * 60" />
            <line v-for="i in 13" :key="`v${i}`" :x1="i * 60" y1="0" :x2="i * 60" y2="600" />
          </g>

          <path
            v-if="pathData"
            :d="pathData"
            fill="none"
            stroke="#409eff"
            stroke-width="3"
            stroke-dasharray="5,5"
          />

          <g
            v-for="exhibit in filteredExhibits"
            :key="exhibit.id"
            class="exhibit-marker"
            :class="{ 'is-selected': isSelected(exhibit), 'in-path': isInPath(exhibit) }"
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
        <div class="legend-item"><span class="legend-dot normal" />普通展品</div>
        <div class="legend-item"><span class="legend-dot in-path" />路线中的展品</div>
        <div class="legend-item"><span class="legend-dot selected" />当前选中</div>
      </div>
    </template>
  </MuseumCard>
</template>

<style scoped>
.floor-map-card {
  height: 100%;
}

.map-controls {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 12px;
}

.map-zoom {
  width: 140px;
}

.map-container {
  height: 460px;
  overflow: auto;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
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
  flex-wrap: wrap;
  gap: 16px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #e4e7ed;
  color: var(--color-text-secondary);
  font-size: 12px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.legend-dot.normal {
  background: #67c23a;
}

.legend-dot.in-path {
  background: #409eff;
}

.legend-dot.selected {
  background: #f56c6c;
}

@media (max-width: 767px) {
  .map-controls {
    flex-direction: column;
    align-items: stretch;
  }

  .map-zoom {
    width: 100%;
  }

  .map-container {
    height: 360px;
  }
}
</style>
