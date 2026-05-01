<script setup>
import { onMounted } from 'vue'
import { useTour } from '../../composables/useTour.js'
import TourStats from './TourStats.vue'
import IdentityTags from './IdentityTags.vue'
import RadarChart from './RadarChart.vue'
import TourOneLiner from './TourOneLiner.vue'

const { tourReport, generateReport, tourSession, reportThemeTitle, loading } = useTour()

onMounted(async () => {
  if (!tourReport.value) {
    await generateReport()
  }
})
</script>

<template>
  <div class="tour-report" :class="`theme-${tourSession?.persona || 'A'}`">
    <div v-if="loading.report" class="loading">
      <el-icon class="is-loading" :size="32"><Loading /></el-icon>
      <span>正在生成你的专属报告...</span>
    </div>
    <template v-if="tourReport">
      <div class="report-header"><h1 class="report-title">{{ reportThemeTitle }}</h1></div>
      <TourStats :report="tourReport" :persona="tourSession?.persona" />
      <IdentityTags :tags="tourReport.identity_tags" />
      <RadarChart :scores="tourReport.radar_scores" />
      <TourOneLiner :text="tourReport.one_liner" />
      <div class="qr-placeholder">
        <p>扫码分享你的导览报告</p>
        <div class="qr-box">QR</div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.tour-report { max-width: 640px; margin: 0 auto; padding: 40px 24px; min-height: 100%; }
.theme-A { background: var(--color-bg-base); }
.theme-B { background: var(--color-bg-base); }
.theme-C { background: var(--color-bg-base); }
.report-header { text-align: center; margin-bottom: 32px; }
.report-title { font-size: 28px; color: var(--color-accent); }
.loading { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px; padding: 80px 0; color: var(--color-accent); }
.qr-placeholder { text-align: center; margin-top: 40px; padding: 24px; color: var(--color-text-muted); }
.qr-box { width: 120px; height: 120px; border: 2px dashed var(--color-border); border-radius: 8px; display: flex; align-items: center; justify-content: center; margin: 12px auto 0; font-size: 24px; color: var(--color-text-muted); }
</style>
