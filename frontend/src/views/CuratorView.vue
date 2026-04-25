<script setup>
import { ref } from 'vue'
import { useCurator } from '../composables/useCurator.js'
import TourPlanner from '../components/curator/TourPlanner.vue'
import TourPathView from '../components/curator/TourPathView.vue'
import FloorMap from '../components/layout/FloorMap.vue'
import { EmptyState, MuseumCard, MuseumPage } from '../design-system/components/index.js'

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
  <MuseumPage class="curator-view">
    <template #hero>
      <h1>导览助手</h1>
      <p>根据你的时间与兴趣自动生成路线，并在地图上追踪每个重点展品。</p>
    </template>

    <div class="curator-main">
      <section class="curator-column planner-column">
        <TourPlanner :loading="loading" @plan="handlePlanTour" />
        <TourPathView
          v-if="currentPath"
          :path="currentPath"
          @select-exhibit="handleSelectExhibit"
          class="path-result"
        />
      </section>

      <section class="curator-column map-column">
        <FloorMap :path="currentPath?.path" :selected-exhibit="selectedExhibit" @select-exhibit="handleSelectExhibit" />
      </section>

      <section class="curator-column detail-column">
        <MuseumCard v-if="selectedExhibit" :title="selectedExhibit.name" subtitle="展品讲解与思考引导" motif="jar">
          <div class="detail-sections">
            <section class="detail-block" v-if="narrative">
              <h4>讲解</h4>
              <p>{{ narrative.output || narrative.narrative }}</p>
            </section>

            <section class="detail-block" v-if="reflection?.questions">
              <h4>思考引导</h4>
              <ul>
                <li v-for="(question, index) in reflection.questions" :key="index">{{ question }}</li>
              </ul>
            </section>
          </div>
        </MuseumCard>

        <EmptyState
          v-else
          icon="fish"
          title="等待选择展品"
          description="在路线或地图中点击任一展品，右侧将展示讲解与思考问题。"
        />
      </section>
    </div>
  </MuseumPage>
</template>

<style scoped>
h1 {
  margin: 0;
  font-size: clamp(22px, 2.8vw, 30px);
  font-family: var(--font-family-display);
}

p {
  margin: 8px 0 0;
  color: var(--color-text-secondary);
  line-height: 1.6;
}

.curator-main {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) minmax(360px, 1.4fr) minmax(260px, 1fr);
  gap: 16px;
}

.curator-column {
  min-width: 0;
}

.path-result {
  margin-top: 16px;
}

.detail-sections {
  display: grid;
  gap: 16px;
}

.detail-block h4 {
  margin: 0 0 8px;
  font-size: 14px;
}

.detail-block p {
  margin: 0;
  line-height: 1.8;
  white-space: pre-wrap;
}

.detail-block ul {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
  color: var(--color-text-secondary);
}

@media (max-width: 1279px) {
  .curator-main {
    grid-template-columns: 1fr 1fr;
  }

  .detail-column {
    grid-column: span 2;
  }
}

@media (max-width: 767px) {
  .curator-main {
    grid-template-columns: 1fr;
  }

  .detail-column {
    grid-column: auto;
  }
}
</style>
