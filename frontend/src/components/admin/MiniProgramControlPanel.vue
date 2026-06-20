<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Document,
  MapLocation,
  Monitor,
  Refresh,
  Search,
} from '@element-plus/icons-vue'
import { api } from '../../api/index.js'
import {
  BANPO_HALLS,
  BANPO_PERSONAS,
  TTS_VOICE_CONTRACT,
  normalizeHallSlug,
} from '../../constants/banpo.js'

const router = useRouter()
const loading = ref(false)
const fetchErrors = ref([])

const halls = ref([])
const exhibits = ref([])
const prompts = ref([])
const ttsPersonas = ref([])
const healthStatus = ref('unknown')
const readyStatus = ref('unknown')

const expectedHalls = BANPO_HALLS.map((hall) => ({
  slug: hall.slug,
  name: hall.name,
  type: hall.type,
  zone: hall.zone,
  owner: '展厅设置',
}))

const personaContract = Object.values(BANPO_PERSONAS).map((persona) => ({
  code: persona.code,
  personaId: persona.personaId,
  label: persona.name,
  report: persona.reportTitle,
  route: persona.routeTitle,
}))

const expectedTtsKeys = BANPO_PERSONAS.map((persona) => `tour_tts_persona_${persona.code.toLowerCase()}`)

const missingExpectedHalls = computed(() => {
  const current = new Set(halls.value.map((hall) => normalizeHallSlug(hall.slug)))
  return expectedHalls.filter((hall) => !current.has(hall.slug))
})

const inactiveExpectedHalls = computed(() => {
  const bySlug = new Map(halls.value.map((hall) => [normalizeHallSlug(hall.slug), hall]))
  return expectedHalls.filter((hall) => bySlug.has(hall.slug) && bySlug.get(hall.slug)?.is_active === false)
})

const hasBingtangVoice = computed(() => {
  if (!hasExactTtsPersonas.value) return false
  return ttsPersonas.value.every((item) => !item.voice || item.voice === TTS_VOICE_CONTRACT.voice)
})

const hasExactTtsPersonas = computed(() => {
  const keys = ttsPersonas.value.map((item) => item.key).sort()
  return keys.length === expectedTtsKeys.length
    && expectedTtsKeys.every((key, index) => keys[index] === key)
})

const dashboardStats = computed(() => [
  {
    label: '后端服务',
    value: healthStatus.value === 'ok' ? '正常' : '待检查',
    desc: readyStatus.value === 'ok' ? 'health / ready 均可用' : 'ready 状态未确认',
    type: healthStatus.value === 'ok' ? 'success' : 'warning',
  },
  {
    label: '展厅契约',
    value: `${expectedHalls.length - missingExpectedHalls.value.length}/${expectedHalls.length}`,
    desc: inactiveExpectedHalls.value.length
      ? `${inactiveExpectedHalls.value.length} 个约定展厅未启用`
      : '按小程序 canonical slug 检查',
    type: missingExpectedHalls.value.length || inactiveExpectedHalls.value.length ? 'warning' : 'success',
  },
  {
    label: '展品数据',
    value: String(exhibits.value.length),
    desc: '影响展品浏览、搜展品和 OCR fallback',
    type: exhibits.value.length ? 'success' : 'warning',
  },
  {
    label: '提示词',
    value: String(prompts.value.length),
    desc: '覆盖 RAG、策展、报告与语音人设',
    type: prompts.value.length ? 'success' : 'warning',
  },
])

const flowRows = computed(() => [
  {
    name: '入口问卷与四身份',
    miniapp: 'onboarding -> persona-reveal -> route',
    backend: '/tour/sessions, persona A/B/C/D',
    control: '提示词管理、语音角色管理',
    status: hasExactTtsPersonas.value ? 'ok' : 'warn',
    note: hasExactTtsPersonas.value ? '四身份 TTS key 与小程序 A/B/C/D 完全一致' : 'TTS 身份必须只保留 tour_tts_persona_a/b/c/d',
    actions: [
      { label: '提示词', path: '/admin/prompts' },
      { label: '语音角色', path: '/admin/tts-personas' },
    ],
  },
  {
    name: 'AI 策展路线',
    miniapp: 'route 页先有可用路线，再接入 AI plan',
    backend: '/curator/plan-tour',
    control: '路线管理、提示词管理、LLM 调用追踪',
    status: healthStatus.value === 'ok' ? 'ok' : 'warn',
    note: '路线管理展示的小程序本地 fallback 为固定 9 站、约 102 分钟；AI plan 可覆盖展示',
    actions: [
      { label: '路线管理', path: '/admin/tour-paths' },
      { label: '调用追踪', path: '/admin/llm-traces' },
    ],
  },
  {
    name: '展厅选择与到访统计',
    miniapp: 'hall 选择、有效互动事件、report halls_visited',
    backend: '/tour/halls, /tour/sessions/:id/events, /report',
    control: '展厅设置',
    status: missingExpectedHalls.value.length ? 'warn' : 'ok',
    note: missingExpectedHalls.value.length
      ? `缺少 ${missingExpectedHalls.value.length} 个小程序约定展厅`
      : '展厅 slug 与小程序 DEFAULT_ORDER 完全一致；hall_enter 不单独计入到访统计',
    actions: [{ label: '展厅设置', path: '/admin/halls' }],
  },
  {
    name: '展品搜索与拍照识别',
    miniapp: 'exhibit-scan 文字搜索/OCR 匹配 -> exhibit-detail',
    backend: '/exhibits, /exhibits/:id',
    control: '展品管理、知识库管理',
    status: exhibits.value.length ? 'ok' : 'warn',
    note: exhibits.value.length ? '展品 API 有数据可供搜索和 OCR 匹配' : '当前未读取到展品数据',
    actions: [
      { label: '展品管理', path: '/admin/exhibits' },
      { label: '知识库', path: '/admin/documents' },
    ],
  },
  {
    name: '建议条与 AI 回答',
    miniapp: 'tour suggestions Phase1/Phase2, SSE Markdown',
    backend: '/tour/sessions/:id/chat/stream, RAG prompts',
    control: '提示词管理、LLM 调用追踪',
    status: prompts.value.length ? 'ok' : 'warn',
    note: '建议条即时规则在小程序端；回答风格、RAG 和报告边界可通过提示词与追踪排查',
    actions: [
      { label: '提示词', path: '/admin/prompts' },
      { label: 'LLM 追踪', path: '/admin/llm-traces' },
    ],
  },
  {
    name: '报告与 Reflection Engine',
    miniapp: 'report 渲染 halls_visited / highlights / reflection / record_notes，并合并本地记录摘要',
    backend: '/tour/sessions/:id/report',
    control: '提示词管理、LLM 调用追踪',
    status: healthStatus.value === 'ok' ? 'ok' : 'warn',
    note: '报告由有效互动事件、展厅、展品、规则式 reflection 与小程序本地 TOUR_RECORD_SUMMARY 共同组成',
    actions: [
      { label: '提示词', path: '/admin/prompts' },
      { label: '调用追踪', path: '/admin/llm-traces' },
    ],
  },
  {
    name: 'TTS 手动播报',
    miniapp: 'tour 页手动播放 AI 回复语音',
    backend: '/tts/synthesize',
    control: '语音角色管理',
    status: hasBingtangVoice.value ? 'ok' : 'warn',
    note: hasBingtangVoice.value ? '四身份仅保留 A/B/C/D，并统一使用冰糖声线' : 'TTS key 或冰糖声线未完全对齐',
    actions: [{ label: '语音角色', path: '/admin/tts-personas' }],
  },
])

const syncRows = [
  {
    area: '展品管理',
    runtime: '小程序通过 /exhibits 和 /exhibits/:id 实时读取后端展品库',
    effect: '保存后立即影响搜展品、展品详情、OCR fallback 和报告展品统计',
    note: '需要绑定 canonical hall slug；未绑定展厅会被小程序筛选、报告和 OCR 逻辑漏掉。',
  },
  {
    area: '展厅设置',
    runtime: '小程序展厅选择页主要使用本地 banpo-halls.js；后端 /tour/halls 用于会话和报告契约',
    effect: '后端展厅状态会影响接口和报告；展厅名称/顺序的前端静态改动仍需发布小程序代码',
    note: '管理端应维护与小程序完全一致的 9 个 canonical slug，不再保留旧 slug。',
  },
  {
    area: '提示词与 TTS',
    runtime: 'AI 回答、报告和 TTS 播报由后端接口读取提示词缓存和 TTS persona',
    effect: '保存后需重载缓存；TTS 角色同步后四身份共用冰糖声线',
    note: '提示词不会自动改小程序页面文案，但会影响后端生成内容和播报风格。',
  },
  {
    area: '路线管理',
    runtime: '小程序 route 页先展示本地 9 站 fallback，再调用 /curator/plan-tour',
    effect: 'AI plan 由后端服务实时返回；本地 fallback 路线要改需发布小程序代码',
    note: '管理端路线页现在展示的是小程序 fallback 契约，用于校验，不是直接写入小程序代码。',
  },
]

const quickActions = [
  { title: '维护展厅顺序', desc: '同步小程序选择页、路线页和报告统计使用的 canonical slug。', icon: MapLocation, path: '/admin/halls' },
  { title: '维护展品与 OCR 匹配', desc: '展品名称、分类、展厅归属会直接影响搜展品和拍照识别结果。', icon: Search, path: '/admin/exhibits' },
  { title: '调整导览提示词', desc: '控制 AI 回答风格、RAG 解释方式和报告文本边界。', icon: Document, path: '/admin/prompts' },
  { title: '排查线上回答', desc: '按调用记录查看 route、tour、report 的模型输入输出和错误。', icon: Monitor, path: '/admin/llm-traces' },
]

async function safeLoad(label, loader) {
  try {
    const result = await loader()
    if (!result?.ok) {
      fetchErrors.value.push(`${label}: ${result?.data?.detail || result?.status || '失败'}`)
      return null
    }
    return result.data
  } catch (err) {
    fetchErrors.value.push(`${label}: ${err instanceof Error ? err.message : '失败'}`)
    return null
  }
}

async function fetchDashboard() {
  loading.value = true
  fetchErrors.value = []
  try {
    const [health, ready, hallData, exhibitData, promptData, ttsData] = await Promise.all([
      safeLoad('健康检查', () => api.health()),
      safeLoad('就绪检查', () => api.ready()),
      safeLoad('展厅设置', () => api.admin.listHalls({ include_inactive: 'true' })),
      safeLoad('展品数据', () => api.admin.listExhibits({ limit: 200 })),
      safeLoad('提示词', () => api.admin.prompts.list({ include_inactive: 'true' })),
      safeLoad('语音角色', () => api.admin.ttsPersonas.list()),
    ])

    healthStatus.value = health ? 'ok' : 'error'
    readyStatus.value = ready ? 'ok' : 'error'
    halls.value = hallData?.halls || []
    exhibits.value = exhibitData?.exhibits || []
    prompts.value = promptData?.prompts || []
    ttsPersonas.value = ttsData?.personas || []
  } finally {
    loading.value = false
  }
}

function go(path) {
  router.push(path)
}

function flowTagType(status) {
  return status === 'ok' ? 'success' : 'warning'
}

function flowTagText(status) {
  return status === 'ok' ? '已对齐' : '需检查'
}

function hallContractStatus(row) {
  const hall = halls.value.find((item) => normalizeHallSlug(item.slug) === row.slug)
  if (!hall) return { type: 'danger', text: '缺失' }
  return hall.is_active === false
    ? { type: 'warning', text: '未启用' }
    : { type: 'success', text: '启用' }
}

onMounted(fetchDashboard)
</script>

<template>
  <div class="mini-program-control" v-loading="loading">
    <section class="control-header">
      <div>
        <p class="eyebrow">MuseAI 管理端</p>
        <h1>小程序闭环控制台</h1>
        <p class="subtitle">
          按小程序实际链路检查后台控制点：问卷、路线、展厅、展品、建议条、TTS、报告与 Reflection Engine。
        </p>
      </div>
      <el-button type="primary" @click="fetchDashboard">
        <el-icon><Refresh /></el-icon>
        刷新状态
      </el-button>
    </section>

    <el-alert
      v-if="fetchErrors.length"
      type="warning"
      :closable="false"
      show-icon
      class="status-alert"
    >
      <template #title>
        有 {{ fetchErrors.length }} 项状态未读取成功，通常是登录权限、后端服务或网络问题。
      </template>
      <div class="error-list">
        <span v-for="item in fetchErrors" :key="item">{{ item }}</span>
      </div>
    </el-alert>

    <section class="stat-grid">
      <article v-for="stat in dashboardStats" :key="stat.label" class="stat-card">
        <div class="stat-label">{{ stat.label }}</div>
        <div class="stat-value">{{ stat.value }}</div>
        <el-tag size="small" :type="stat.type">{{ stat.desc }}</el-tag>
      </article>
    </section>

    <section class="panel-section">
      <div class="section-title">
        <div>
          <h2>闭环能力对齐</h2>
          <p>小程序端每个功能都需要能在后台找到对应的数据、配置或排查入口。</p>
        </div>
      </div>

      <div class="flow-list">
        <article v-for="row in flowRows" :key="row.name" class="flow-card">
          <div class="flow-card-head">
            <h3>{{ row.name }}</h3>
            <el-tag :type="flowTagType(row.status)" size="small">{{ flowTagText(row.status) }}</el-tag>
          </div>
          <div class="flow-grid">
            <div class="flow-field">
              <span>小程序链路</span>
              <p>{{ row.miniapp }}</p>
            </div>
            <div class="flow-field">
              <span>后端契约</span>
              <p>{{ row.backend }}</p>
            </div>
            <div class="flow-field">
              <span>管理端控制点</span>
              <p>{{ row.control }}</p>
            </div>
            <div class="flow-field flow-note">
              <span>说明</span>
              <p>{{ row.note }}</p>
            </div>
          </div>
          <div class="action-group">
            <el-button
              v-for="action in row.actions"
              :key="action.path + action.label"
              size="small"
              @click="go(action.path)"
            >
              {{ action.label }}
            </el-button>
          </div>
        </article>
      </div>
    </section>

    <section class="panel-section">
      <div class="section-title">
        <div>
          <h2>管理同步边界</h2>
          <p>这里区分“保存后立即影响小程序”和“需要发布小程序代码”的配置。</p>
        </div>
      </div>
      <div class="sync-list">
        <article v-for="row in syncRows" :key="row.area" class="sync-card">
          <h3>{{ row.area }}</h3>
          <div class="sync-grid">
            <div class="flow-field">
              <span>小程序读取方式</span>
              <p>{{ row.runtime }}</p>
            </div>
            <div class="flow-field">
              <span>生效方式</span>
              <p>{{ row.effect }}</p>
            </div>
            <div class="flow-field">
              <span>说明</span>
              <p>{{ row.note }}</p>
            </div>
          </div>
        </article>
      </div>
    </section>

    <section class="two-column">
      <div class="panel-section">
        <div class="section-title compact">
          <div>
            <h2>四身份契约</h2>
            <p>与小程序 persona、报告标题和路线主题保持一致。</p>
          </div>
          <el-button text type="primary" @click="go('/admin/tts-personas')">
            管理语音角色
          </el-button>
        </div>
        <div class="contract-list">
          <article v-for="row in personaContract" :key="row.code" class="contract-card">
            <div class="contract-main">
              <strong>{{ row.label }}</strong>
              <span>{{ row.report }}</span>
            </div>
            <div class="contract-meta">
              <span>后端 {{ row.code }}</span>
              <span>前端 {{ row.personaId }}</span>
              <span>{{ row.route }}</span>
            </div>
          </article>
        </div>
      </div>

      <div class="panel-section">
        <div class="section-title compact">
          <div>
            <h2>展厅 slug 契约</h2>
            <p>报告统计、路线、展品筛选都应使用这些 canonical slug。</p>
          </div>
          <el-button text type="primary" @click="go('/admin/halls')">
            管理展厅
          </el-button>
        </div>
        <div class="contract-list hall-contract-list">
          <article v-for="row in expectedHalls" :key="row.slug" class="contract-card hall-card">
            <div class="contract-main">
              <strong>{{ row.name }}</strong>
              <span>{{ row.slug }}</span>
            </div>
            <div class="contract-meta">
              <span>{{ row.type }}</span>
              <span>{{ row.zone }}</span>
              <el-tag :type="hallContractStatus(row).type" size="small">
                {{ hallContractStatus(row).text }}
              </el-tag>
            </div>
          </article>
        </div>
      </div>
    </section>

    <section class="quick-grid">
      <button
        v-for="item in quickActions"
        :key="item.title"
        type="button"
        class="quick-card"
        @click="go(item.path)"
      >
        <el-icon><component :is="item.icon" /></el-icon>
        <span class="quick-title">{{ item.title }}</span>
        <span class="quick-desc">{{ item.desc }}</span>
      </button>
    </section>
  </div>
</template>

<style scoped>
.mini-program-control {
  display: grid;
  gap: 18px;
  min-height: 100%;
  padding: 24px;
  background: var(--el-bg-color-page);
}

.control-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.eyebrow {
  margin: 0 0 6px;
  color: var(--el-color-primary);
  font-size: 13px;
  font-weight: 600;
}

h1,
h2 {
  margin: 0;
  color: var(--el-text-color-primary);
}

h1 {
  font-size: 26px;
  line-height: 1.25;
}

h2 {
  font-size: 17px;
}

.subtitle,
.section-title p {
  margin: 6px 0 0;
  color: var(--el-text-color-secondary);
  line-height: 1.55;
}

.status-alert {
  border-radius: 8px;
}

.error-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 6px;
}

.error-list span {
  font-size: 12px;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.stat-card,
.panel-section {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  box-shadow: var(--el-box-shadow-lighter);
}

.stat-card {
  display: grid;
  gap: 8px;
  padding: 16px;
}

.stat-label {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.stat-value {
  color: var(--el-text-color-primary);
  font-size: 24px;
  font-weight: 700;
}

.panel-section {
  min-width: 0;
  padding: 16px;
}

.section-title {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.section-title.compact {
  align-items: center;
}

.action-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.flow-list,
.sync-list,
.contract-list {
  display: grid;
  gap: 12px;
}

.flow-card,
.sync-card,
.contract-card {
  min-width: 0;
  padding: 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-extra-light);
}

.flow-card-head,
.contract-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.flow-card h3,
.sync-card h3 {
  margin: 0;
  color: var(--el-text-color-primary);
  font-size: 16px;
  line-height: 1.35;
}

.flow-grid,
.sync-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 12px 0;
}

.sync-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-bottom: 0;
}

.flow-field {
  min-width: 0;
}

.flow-field span {
  display: block;
  margin-bottom: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 700;
}

.flow-field p {
  margin: 0;
  color: var(--el-text-color-primary);
  line-height: 1.6;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.flow-note {
  grid-column: auto;
}

.contract-list {
  max-height: 390px;
  overflow-y: auto;
  padding-right: 4px;
}

.contract-main {
  display: grid;
  min-width: 0;
  gap: 4px;
}

.contract-main strong {
  color: var(--el-text-color-primary);
  line-height: 1.4;
}

.contract-main span,
.contract-meta {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.contract-meta {
  display: flex;
  flex: 0 1 58%;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 6px 10px;
}

.contract-meta span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.two-column {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr);
  gap: 18px;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.quick-card {
  display: grid;
  gap: 8px;
  min-height: 112px;
  padding: 16px;
  color: var(--el-text-color-primary);
  text-align: left;
  cursor: pointer;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.quick-card:hover {
  border-color: var(--el-color-primary);
  box-shadow: var(--el-box-shadow-light);
}

.quick-card .el-icon {
  color: var(--el-color-primary);
  font-size: 22px;
}

.quick-title {
  font-weight: 700;
}

.quick-desc {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.5;
}

@media (max-width: 1180px) {
  .stat-grid,
  .quick-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .two-column {
    grid-template-columns: 1fr;
  }

  .flow-grid,
  .sync-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .mini-program-control {
    padding: 16px;
  }

  .control-header,
  .section-title {
    flex-direction: column;
  }

  .stat-grid,
  .quick-grid {
    grid-template-columns: 1fr;
  }

  .flow-grid,
  .sync-grid {
    grid-template-columns: 1fr;
  }

  .flow-card-head,
  .contract-card {
    flex-direction: column;
  }

  .contract-meta {
    justify-content: flex-start;
    flex-basis: auto;
  }
}
</style>
