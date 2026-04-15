<script setup>
const props = defineProps({ report: Object, persona: String })

const statTexts = {
  A: {
    duration: (min) => `本次实地勘探总耗时 ${Math.floor(min / 60)}小时${Math.floor(min % 60)}分。`,
    exhibit: (name) => `你的目光在 ${name} 前锁定了最久，完成了深度的数据采集。`,
    hall: (name, dur) => `${name} 是你今日的核心作业区块，长达 ${dur} 分钟的驻足，证明了你对地层学有着极度敏锐的嗅觉。`,
  },
  B: {
    duration: (min) => `这次串门你一共逛了 ${Math.floor(min / 60)}小时${Math.floor(min % 60)}分。`,
    exhibit: (name) => `全村那么多宝贝，你偏偏对着 ${name} 挪不开眼，是不是想起了当年阿妈用它的样子？`,
    hall: (name, dur) => `你在 ${name} 待了足足 ${dur} 分钟，一定是闻到了那股熟悉的泥土味吧。`,
  },
  C: {
    duration: (min) => `本次沉浸式游学共计 ${Math.floor(min / 60)}小时${Math.floor(min % 60)}分。`,
    exhibit: (name) => `面对众多的史前谜题，你将"最佳观察奖"颁给了 ${name}。`,
    hall: (name, dur) => `在 ${name} 的 ${dur} 分钟里，你展现出了远超常人的求知欲。`,
  },
}
</script>

<template>
  <div class="tour-stats">
    <div class="stat-item">
      <p class="stat-text">{{ (statTexts[persona || 'A'])?.duration?.(report?.total_duration_minutes || 0) }}</p>
    </div>
    <div v-if="report?.most_viewed_exhibit_id" class="stat-item">
      <p class="stat-text">{{ (statTexts[persona || 'A'])?.exhibit?.(report.most_viewed_exhibit_id) }}</p>
    </div>
    <div v-if="report?.longest_hall" class="stat-item">
      <p class="stat-text">{{ (statTexts[persona || 'A'])?.hall?.(report.longest_hall, Math.floor((report.longest_hall_duration || 0) / 60)) }}</p>
    </div>
  </div>
</template>

<style scoped>
.tour-stats { margin-bottom: 32px; }
.stat-item { padding: 16px; background: rgba(255,255,255,0.04); border-radius: 8px; margin-bottom: 12px; }
.stat-text { font-size: 15px; line-height: 1.8; color: #f0e6d3; }
</style>
