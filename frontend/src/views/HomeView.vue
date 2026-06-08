<script setup>
import { computed, inject } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../composables/useAuth.js'
import { MuseumPage } from '../design-system/components/index.js'

const router = useRouter()
const showAuthModal = inject('showAuthModal', () => {})
const { isAuthenticated, isAdmin } = useAuth()

const primaryActionText = computed(() => {
  if (!isAuthenticated.value) return '登录管理端'
  if (isAdmin.value) return '进入管理后台'
  return '开始导览测试'
})

const cards = [
  {
    title: '小程序闭环',
    desc: '查看问卷、路线、展厅、展品、TTS 与报告的整体对齐状态。',
    path: '/admin/overview',
    admin: true,
  },
  {
    title: '展厅设置',
    desc: '维护半坡常开放展厅、临展厅顺序与中文展示名称。',
    path: '/admin/halls',
    admin: true,
  },
  {
    title: '展品管理',
    desc: '检查展品、别名、分类、所属展厅与小程序搜展品结果。',
    path: '/admin/exhibits',
    admin: true,
  },
  {
    title: '提示词管理',
    desc: '维护导览回答、建议条、反身性报告与 RAG 生成提示词。',
    path: '/admin/prompts',
    admin: true,
  },
  {
    title: 'AI 导览测试',
    desc: '使用 Web 端快速验证导览对话和后端服务状态。',
    path: '/tour',
    admin: false,
  },
  {
    title: '展品浏览',
    desc: '从管理端检查展品列表、展厅筛选和前后端数据契约。',
    path: '/exhibits',
    admin: false,
  },
]

function handlePrimaryAction() {
  if (!isAuthenticated.value) {
    showAuthModal(true)
    return
  }
  router.push(isAdmin.value ? '/admin/overview' : '/tour')
}

function goToCard(card) {
  if (card.admin && !isAdmin.value) {
    if (!isAuthenticated.value) {
      showAuthModal(true)
    }
    return
  }
  router.push(card.path)
}
</script>

<template>
  <MuseumPage class="home-view">
    <section class="home-hero">
      <div>
        <p class="eyebrow">MuseAI 管理工作台</p>
        <h1>半坡博物馆 AI 导览管理端</h1>
        <p class="hero-desc">
          当前管理端用于对齐小程序的展厅、展品、路线、提示词、TTS 和报告闭环。
        </p>
      </div>
      <el-button type="warning" size="large" @click="handlePrimaryAction">
        {{ primaryActionText }}
      </el-button>
    </section>

    <section class="status-grid">
      <div class="status-card">
        <span>小程序能力</span>
        <strong>问卷 / 路线 / 导览 / 报告</strong>
      </div>
      <div class="status-card">
        <span>当前数据</span>
        <strong>半坡展厅与展品契约</strong>
      </div>
      <div class="status-card">
        <span>临时访问</span>
        <strong>IP:8080 管理端</strong>
      </div>
    </section>

    <section class="entry-grid">
      <article
        v-for="card in cards"
        :key="card.path"
        class="entry-card"
        :class="{ 'entry-card--disabled': card.admin && !isAdmin }"
        @click="goToCard(card)"
      >
        <h2>{{ card.title }}</h2>
        <p>{{ card.desc }}</p>
        <span>{{ card.admin && !isAdmin ? '需要管理员权限' : '打开' }}</span>
      </article>
    </section>
  </MuseumPage>
</template>

<style scoped>
.home-view {
  min-height: 100%;
}

.home-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-fluid-md);
  padding: var(--space-fluid-md);
  border: 1px solid rgba(203, 125, 83, 0.22);
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, rgba(255, 252, 247, 0.98), rgba(248, 239, 228, 0.78));
}

.eyebrow {
  margin: 0 0 8px;
  color: var(--color-accent);
  font-weight: var(--font-weight-semibold);
}

.home-hero h1 {
  margin: 0;
  font-family: var(--font-family-base);
  font-size: clamp(28px, 4vw, 42px);
  letter-spacing: 0;
}

.hero-desc {
  max-width: 680px;
  margin: 12px 0 0;
  color: var(--color-text-secondary);
  line-height: 1.7;
}

.status-grid,
.entry-grid {
  display: grid;
  gap: var(--space-4);
  margin-top: var(--space-fluid-md);
}

.status-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.status-card,
.entry-card {
  border: 1px solid rgba(77, 51, 31, 0.1);
  border-radius: var(--radius-md);
  background: var(--color-bg-elevated);
}

.status-card {
  padding: var(--space-4);
}

.status-card span,
.entry-card p,
.entry-card span {
  color: var(--color-text-secondary);
}

.status-card strong {
  display: block;
  margin-top: 8px;
  color: var(--color-text-primary);
}

.entry-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.entry-card {
  min-height: 150px;
  padding: var(--space-5);
  cursor: pointer;
  transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
}

.entry-card:hover {
  transform: translateY(-2px);
  border-color: rgba(203, 125, 83, 0.42);
  box-shadow: 0 14px 32px rgba(79, 52, 32, 0.08);
}

.entry-card h2 {
  margin: 0 0 10px;
  font-size: 20px;
}

.entry-card p {
  min-height: 52px;
  margin: 0 0 18px;
  line-height: 1.6;
}

.entry-card span {
  font-weight: var(--font-weight-semibold);
}

.entry-card--disabled {
  cursor: not-allowed;
  opacity: 0.62;
}

.entry-card--disabled:hover {
  transform: none;
  box-shadow: none;
}

@media (max-width: 960px) {
  .home-hero {
    align-items: flex-start;
    flex-direction: column;
  }

  .status-grid,
  .entry-grid {
    grid-template-columns: 1fr;
  }
}
</style>
