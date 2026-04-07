<script setup>
import { ref, onMounted } from 'vue'
import { useExhibits } from '../composables/useExhibits.js'
import ExhibitList from '../components/exhibits/ExhibitList.vue'
import ExhibitFilter from '../components/exhibits/ExhibitFilter.vue'
import FloorMap from '../components/layout/FloorMap.vue'

const { exhibits, loading, fetchExhibits } = useExhibits()

const selectedExhibit = ref(null)
const viewMode = ref('list') // 'list' | 'map'

onMounted(() => fetchExhibits())

function handleFilter(filters) {
  // Build params object with all filters
  const params = {}
  if (filters.category) params.category = filters.category
  if (filters.hall) params.hall = filters.hall
  if (filters.keyword) params.search = filters.keyword

  fetchExhibits(params)
}
</script>

<template>
  <div class="exhibits-view">
    <el-row :gutter="20">
      <el-col :span="6">
        <ExhibitFilter @filter="handleFilter" />
      </el-col>

      <el-col :span="18">
        <el-tabs v-model="viewMode">
          <el-tab-pane label="列表视图" name="list">
            <ExhibitList
              :exhibits="exhibits"
              :loading="loading"
              @select="selectedExhibit = $event"
            />
          </el-tab-pane>

          <el-tab-pane label="地图视图" name="map">
            <FloorMap
              :exhibits="exhibits"
              :selected-exhibit="selectedExhibit"
              @select-exhibit="selectedExhibit = $event"
            />
          </el-tab-pane>
        </el-tabs>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.exhibits-view {
  height: 100%;
}
</style>
