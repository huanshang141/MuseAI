<script setup>
import { computed, onMounted } from 'vue'
import { useTour } from '../../composables/useTour.js'

const { halls, fetchHalls, selectHall, tourStep } = useTour()

const openHalls = computed(() => halls.value.filter((hall) => hall.is_active !== false))

async function onHallSelect(hallSlug) {
  await selectHall(hallSlug)
  tourStep.value = 'tour'
}

onMounted(async () => {
  if (!halls.value.length) {
    await fetchHalls()
  }
})
</script>

<template>
  <div class="hall-select">
    <section class="hero">
      <span class="kicker">半坡导览</span>
      <h1>选择探索区域</h1>
      <p>管理端与小程序使用同一套半坡展厅契约。常开放展厅优先展示，临展厅排在最后，便于现场按真实可参观区域组织导览。</p>
    </section>

    <section class="hall-grid">
      <article
        v-for="hall in openHalls"
        :key="hall.slug"
        class="hall-card"
        :class="{ temporary: hall.type === '临展' }"
        @click="onHallSelect(hall.slug)"
      >
        <div class="hall-icon">{{ hall.icon }}</div>
        <div class="hall-body">
          <div class="hall-meta">
            <el-tag size="small" effect="plain">{{ hall.type }}</el-tag>
            <span>{{ hall.zone }}</span>
          </div>
          <h2>{{ hall.name }}</h2>
          <p>{{ hall.description }}</p>
          <div class="hall-tags">
            <span v-for="tag in hall.highlights.slice(0, 4)" :key="tag">{{ tag }}</span>
          </div>
        </div>
        <div class="hall-stat">
          <strong>{{ hall.exhibit_count || 0 }}</strong>
          <span>展品</span>
          <strong>{{ hall.estimated_duration_minutes }}</strong>
          <span>分钟</span>
        </div>
      </article>
    </section>
  </div>
</template>

<style scoped>
.hall-select {
  min-height: 100%;
  padding: 48px 28px;
  background:
    radial-gradient(circle at 14% 4%, rgba(203, 126, 82, 0.13), transparent 28%),
    linear-gradient(180deg, #fffdf8 0%, #f7f0e8 100%);
}

.hero {
  max-width: 1120px;
  margin: 0 auto 30px;
}

.kicker {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: #f4e5d7;
  color: #b76b41;
  font-size: 13px;
  font-weight: 700;
}

.hero h1 {
  margin: 16px 0 10px;
  font-size: 34px;
  line-height: 1.18;
  color: #2e2119;
  letter-spacing: 0;
}

.hero p {
  max-width: 680px;
  margin: 0;
  color: #7f6b5b;
  font-size: 15px;
  line-height: 1.8;
}

.hall-grid {
  max-width: 1120px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 18px;
}

.hall-card {
  display: grid;
  grid-template-columns: 66px 1fr auto;
  gap: 18px;
  align-items: start;
  padding: 22px;
  min-height: 164px;
  border: 1px solid rgba(125, 92, 68, 0.16);
  border-radius: 14px;
  background: rgba(255, 252, 247, 0.94);
  box-shadow: 0 16px 40px rgba(68, 43, 25, 0.08);
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}

.hall-card:hover {
  transform: translateY(-3px);
  border-color: rgba(200, 121, 74, 0.62);
  box-shadow: 0 20px 48px rgba(68, 43, 25, 0.13);
}

.hall-card.temporary {
  background: rgba(250, 246, 239, 0.78);
}

.hall-icon {
  display: grid;
  place-items: center;
  width: 66px;
  height: 66px;
  border-radius: 14px;
  background: #f2e6d6;
  font-size: 32px;
}

.hall-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  color: #a28a78;
  font-size: 13px;
}

.hall-body h2 {
  margin: 0 0 8px;
  color: #33241b;
  font-size: 21px;
  letter-spacing: 0;
}

.hall-body p {
  margin: 0;
  color: #6f5d50;
  line-height: 1.7;
}

.hall-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.hall-tags span {
  padding: 5px 10px;
  border-radius: 999px;
  background: #f4e8d9;
  color: #a46a47;
  font-size: 12px;
}

.hall-stat {
  display: grid;
  grid-template-columns: auto auto;
  gap: 2px 6px;
  align-items: baseline;
  color: #9a7d66;
  font-size: 12px;
  white-space: nowrap;
}

.hall-stat strong {
  color: #34241a;
  font-size: 18px;
}

@media (max-width: 768px) {
  .hall-select {
    padding: 28px 16px;
  }

  .hero h1 {
    font-size: 28px;
  }

  .hall-grid {
    grid-template-columns: 1fr;
  }

  .hall-card {
    grid-template-columns: 58px 1fr;
  }

  .hall-icon {
    width: 58px;
    height: 58px;
  }

  .hall-stat {
    grid-column: 2;
    display: flex;
    gap: 5px;
  }
}
</style>
