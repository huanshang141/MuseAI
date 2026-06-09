<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { api } from '../../api/index.js'
import {
  BANPO_PERSONAS,
  BANPO_ROUTE_STRATEGIES,
  getHallDisplayName,
} from '../../constants/banpo.js'

const activePersona = ref('D')
const manualRoutes = ref([])
const loading = ref(false)

const currentPersona = computed(() => BANPO_PERSONAS.find((persona) => persona.code === activePersona.value))
const currentRoute = computed(() => BANPO_ROUTE_STRATEGIES[activePersona.value])
const totalMinutes = computed(() => currentRoute.value?.steps.reduce((sum, step) => sum + step.minutes, 0) || 0)

onMounted(fetchManualRoutes)

async function fetchManualRoutes() {
  loading.value = true
  try {
    const result = await api.admin.listTourPaths()
    if (result.ok) {
      manualRoutes.value = result.data.tour_paths || result.data || []
    } else {
      manualRoutes.value = []
    }
  } catch {
    ElMessage.warning('人工路线接口暂不可用，当前展示本地兜底契约')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="tour-path-manager">
    <header class="admin-hero">
      <div>
        <span class="kicker">路线契约</span>
        <h2>AI 策展路线与本地兜底</h2>
        <p>小程序路线页优先调用 <code>/curator/plan-tour</code> 生成结构化路线。这里展示与小程序 <code>route.js</code> 完全一致的 9 站本地兜底路线，用于网络失败、接口异常或人工验收时保持体验完整。</p>
      </div>
      <el-button :loading="loading" @click="fetchManualRoutes">刷新人工路线</el-button>
    </header>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="route-alert"
      title="不会覆盖小程序 AI 路线"
    >
      <template #default>
        管理端此页用于查看和校验路线契约。真正的个性化顺序由后端 curator service 根据 persona、时间和问卷兴趣实时生成；本地兜底路线不按身份改顺序。
      </template>
    </el-alert>

    <section class="persona-tabs">
      <button
        v-for="persona in BANPO_PERSONAS"
        :key="persona.code"
        class="persona-tab"
        :class="{ active: persona.code === activePersona }"
        @click="activePersona = persona.code"
      >
        <span>{{ persona.icon }}</span>
        <strong>{{ persona.name }}</strong>
        <small>{{ persona.routeTitle }}</small>
      </button>
    </section>

    <section class="route-summary" v-if="currentRoute">
      <div>
        <span class="kicker">{{ currentPersona?.focusTitle }}</span>
        <h3>{{ currentRoute.title }}</h3>
        <p>{{ currentRoute.summary }}</p>
      </div>
      <div class="route-metrics">
        <div>
          <strong>{{ currentRoute.steps.length }}</strong>
          <span>展厅节点</span>
        </div>
        <div>
          <strong>{{ totalMinutes }}</strong>
          <span>分钟</span>
        </div>
      </div>
    </section>

    <section class="route-steps" v-if="currentRoute">
      <article v-for="step in currentRoute.steps" :key="step.order" class="route-step">
        <div class="step-index">{{ step.order }}</div>
        <div class="step-body">
          <div class="step-header">
            <span>第 {{ step.order }} 站</span>
            <strong>{{ getHallDisplayName(step.hall_slug) }}</strong>
            <em>约 {{ step.minutes }} 分钟</em>
          </div>
          <h4>{{ step.title }}</h4>
          <p>{{ step.reason }}</p>
          <div class="focus-box">
            <span>重点关注</span>
            <strong>{{ step.focus }}</strong>
          </div>
          <div class="step-tags">
            <span v-for="tag in step.tags" :key="tag">{{ tag }}</span>
          </div>
        </div>
      </article>
    </section>

    <section class="manual-routes">
      <div class="section-title">
        <h3>人工路线记录</h3>
        <span>{{ manualRoutes.length }} 条</span>
      </div>
      <el-empty
        v-if="!manualRoutes.length"
        description="当前没有单独维护人工路线；小程序会使用 AI 策展路线和 9 站本地兜底路线。"
      />
      <el-table v-else :data="manualRoutes" border>
        <el-table-column prop="name" label="路线名称" min-width="160" />
        <el-table-column prop="description" label="说明" min-width="260" />
        <el-table-column prop="estimated_duration" label="时长" width="110">
          <template #default="{ row }">{{ row.estimated_duration || '-' }} 分钟</template>
        </el-table-column>
        <el-table-column prop="exhibit_count" label="展项数" width="100" />
      </el-table>
    </section>
  </div>
</template>

<style scoped>
.tour-path-manager {
  min-height: 100%;
  padding: 28px 34px 56px;
  background: linear-gradient(180deg, #fffdf9 0%, #f8f2ea 100%);
}

.admin-hero,
.route-summary,
.manual-routes {
  border: 1px solid rgba(126, 91, 65, 0.16);
  border-radius: 16px;
  background: #fffaf3;
  box-shadow: 0 14px 36px rgba(77, 49, 31, 0.07);
}

.admin-hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 24px;
  margin-bottom: 16px;
}

.kicker {
  color: #c57548;
  font-size: 13px;
  font-weight: 700;
}

.admin-hero h2,
.route-summary h3 {
  margin: 8px 0;
  color: #2f2118;
  font-size: 28px;
}

.admin-hero p,
.route-summary p {
  max-width: 760px;
  margin: 0;
  color: #7e6a59;
  line-height: 1.7;
}

.route-alert {
  margin-bottom: 18px;
}

.persona-tabs {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.persona-tab {
  display: grid;
  gap: 6px;
  justify-items: start;
  padding: 18px;
  border: 1px solid rgba(126, 91, 65, 0.16);
  border-radius: 14px;
  background: rgba(255, 252, 247, 0.88);
  color: #33241b;
  text-align: left;
  cursor: pointer;
}

.persona-tab span {
  font-size: 26px;
}

.persona-tab strong {
  font-size: 17px;
}

.persona-tab small {
  color: #937967;
}

.persona-tab.active {
  border-color: #c57548;
  background: #fff6ed;
  box-shadow: 0 12px 28px rgba(180, 98, 58, 0.12);
}

.route-summary {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 24px;
  margin-bottom: 20px;
}

.route-metrics {
  display: flex;
  gap: 12px;
}

.route-metrics div {
  min-width: 92px;
  padding: 14px 16px;
  border-radius: 12px;
  background: #f5eadb;
}

.route-metrics strong {
  display: block;
  color: #2f2118;
  font-size: 26px;
}

.route-metrics span {
  color: #947a64;
  font-size: 13px;
}

.route-steps {
  display: grid;
  gap: 16px;
  margin-bottom: 22px;
}

.route-step {
  display: grid;
  grid-template-columns: 48px 1fr;
  gap: 16px;
}

.step-index {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 50%;
  background: #d09a63;
  color: white;
  font-weight: 800;
}

.step-body {
  padding: 20px;
  border: 1px solid rgba(126, 91, 65, 0.16);
  border-radius: 16px;
  background: rgba(255, 252, 247, 0.92);
}

.step-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  color: #9a806b;
}

.step-header strong {
  color: #2f2118;
  font-size: 18px;
}

.step-header em {
  margin-left: auto;
  font-style: normal;
}

.step-body h4 {
  margin: 10px 0 6px;
  color: #2f2118;
  font-size: 20px;
}

.step-body p {
  margin: 0 0 12px;
  color: #756252;
  line-height: 1.7;
}

.focus-box {
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border-left: 3px solid #c57548;
  background: #f7efe6;
}

.focus-box span {
  color: #c57548;
  font-size: 12px;
  font-weight: 700;
}

.focus-box strong {
  color: #3a2a20;
}

.step-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.step-tags span {
  padding: 5px 10px;
  border-radius: 999px;
  background: #f2e4d2;
  color: #a66d49;
  font-size: 12px;
}

.manual-routes {
  padding: 20px;
}

.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.section-title h3 {
  margin: 0;
  color: #2f2118;
}

.section-title span {
  color: #9a806b;
}

@media (max-width: 1080px) {
  .persona-tabs {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .admin-hero,
  .route-summary {
    flex-direction: column;
  }
}
</style>
