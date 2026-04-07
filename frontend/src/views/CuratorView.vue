<script setup>
import { ref } from 'vue'
import { useCurator } from '../composables/useCurator.js'
import TourPlanner from '../components/curator/TourPlanner.vue'
import TourPathView from '../components/curator/TourPathView.vue'
import FloorMap from '../components/layout/FloorMap.vue'

const { loading, planTour, generateNarrative, getReflectionPrompts } = useCurator()

const currentPath = ref(null)
const selectedExhibit = ref(null)
const narrative = ref(null)
const reflection = ref(null)

async function handlePlanTour(planData) {
  const result = await planTour(planData.availableTime, planData.interests)
  if (result) {
    currentPath.value = result
  }
}

async function handleSelectExhibit(exhibit) {
  selectedExhibit.value = exhibit
  narrative.value = await generateNarrative(exhibit.id)
  reflection.value = await getReflectionPrompts(exhibit.id)
}
</script>

<template>
  <div class="curator-view">
    <el-row :gutter="20">
      <!-- Left: Tour Planner -->
      <el-col :span="8">
        <TourPlanner
          :loading="loading"
          @plan="handlePlanTour"
        />

        <!-- Path Result -->
        <TourPathView
          v-if="currentPath"
          :path="currentPath"
          @select-exhibit="handleSelectExhibit"
          class="path-result"
        />
      </el-col>

      <!-- Center: Floor Map -->
      <el-col :span="10">
        <FloorMap
          :path="currentPath?.path"
          :selected-exhibit="selectedExhibit"
          @select-exhibit="handleSelectExhibit"
        />
      </el-col>

      <!-- Right: Exhibit Detail -->
      <el-col :span="6">
        <div v-if="selectedExhibit" class="exhibit-detail-panel">
          <h3>{{ selectedExhibit.name }}</h3>

          <!-- Narrative -->
          <el-card v-if="narrative" class="narrative-card">
            <template #header>讲解</template>
            <div class="narrative-content">
              {{ narrative.output || narrative.narrative }}
            </div>
          </el-card>

          <!-- Reflection -->
          <el-card v-if="reflection?.questions" class="reflection-card">
            <template #header>思考引导</template>
            <ul>
              <li v-for="(q, i) in reflection.questions" :key="i">
                {{ q }}
              </li>
            </ul>
          </el-card>
        </div>

        <el-empty v-else description="选择展品查看详情" />
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.curator-view {
  height: 100%;
}

.path-result {
  margin-top: 20px;
}

.exhibit-detail-panel {
  height: 100%;
  overflow-y: auto;
}

.narrative-card,
.reflection-card {
  margin-top: 16px;
}

.narrative-content {
  line-height: 1.8;
  white-space: pre-wrap;
}
</style>
