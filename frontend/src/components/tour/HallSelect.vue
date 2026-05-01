<script setup>
import { useTour } from '../../composables/useTour.js'

const { halls, selectHall, tourStep } = useTour()

const hallIcons = { 'relic-hall': '🏺', 'site-hall': '🏚️' }

async function onHallSelect(hallSlug) {
  await selectHall(hallSlug)
  tourStep.value = 'tour'
}
</script>

<template>
  <div class="hall-select">
    <div class="hall-select-inner">
      <h2 class="title">选择你想先参观的展厅</h2>
      <p class="subtitle">每个展厅都有独特的展品和故事等你发现</p>
      <div class="hall-cards">
        <div v-for="hall in halls" :key="hall.slug" class="hall-card" @click="onHallSelect(hall.slug)">
          <div class="hall-icon">{{ hallIcons[hall.slug] || '🏛️' }}</div>
          <h3 class="hall-name">{{ hall.name }}</h3>
          <p class="hall-desc">{{ hall.description }}</p>
          <div class="hall-meta">
            <span>{{ hall.exhibit_count }} 件展品</span>
            <span>约 {{ hall.estimated_duration_minutes }} 分钟</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.hall-select { display: flex; justify-content: center; align-items: center; min-height: 100%; padding: 40px 20px; }
.hall-select-inner { max-width: 800px; width: 100%; text-align: center; }
.title { font-size: 24px; color: var(--color-text-primary); margin-bottom: 8px; }
.subtitle { font-size: 15px; color: var(--color-text-muted); margin-bottom: 40px; }
.hall-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 24px; }
.hall-card { padding: 32px 24px; background: var(--color-bg-elevated); border: 1px solid var(--color-border); border-radius: 16px; cursor: pointer; transition: all 0.2s; text-align: center; }
.hall-card:hover { background: var(--color-accent-muted); border-color: var(--color-accent); transform: translateY(-4px); }
.hall-icon { font-size: 48px; margin-bottom: 16px; }
.hall-name { font-size: 20px; color: var(--color-text-primary); margin-bottom: 12px; }
.hall-desc { font-size: 14px; line-height: 1.8; color: var(--color-text-secondary); margin-bottom: 16px; }
.hall-meta { display: flex; justify-content: center; gap: 16px; font-size: 13px; color: var(--color-accent); }
</style>
