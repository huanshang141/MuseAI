<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../../api/index.js'
import { ElMessage } from 'element-plus'
import {
  Search,
  Refresh,
  View,
  Timer,
  Cpu,
  DocumentCopy,
  Check,
  Close
} from '@element-plus/icons-vue'

// State
const loading = ref(false)
const traces = ref([])
const total = ref(0)
const limit = ref(20)
const offset = ref(0)
const detailVisible = ref(false)
const currentTrace = ref(null)

// Filters
const filters = ref({
  source: '',
  model: '',
  status: '',
  trace_id: '',
})

const statusOptions = [
  { value: 'success', label: '成功' },
  { value: 'error', label: '错误' },
]

// Computed
const hasFilters = computed(() =>
  Object.values(filters.value).some(v => v !== '')
)

const currentPage = computed(() => Math.floor(offset.value / limit.value) + 1)

// Methods
function buildQueryParams() {
  const params = { limit: limit.value, offset: offset.value }
  if (filters.value.source) params.source = filters.value.source
  if (filters.value.model) params.model = filters.value.model
  if (filters.value.status) params.status = filters.value.status
  if (filters.value.trace_id) params.trace_id = filters.value.trace_id
  return params
}

async function fetchTraces() {
  loading.value = true
  try {
    const result = await api.admin.llmTraces.list(buildQueryParams())
    if (result.ok) {
      traces.value = result.data.items || []
      total.value = result.data.total || 0
      limit.value = result.data.limit || 20
      offset.value = result.data.offset || 0
    } else {
      ElMessage.error(result.data?.detail || '获取调用记录失败')
    }
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  offset.value = 0
  fetchTraces()
}

function handleReset() {
  filters.value = { source: '', model: '', status: '', trace_id: '' }
  offset.value = 0
  fetchTraces()
}

function handlePageChange(page) {
  offset.value = (page - 1) * limit.value
  fetchTraces()
}

function handleSizeChange(size) {
  limit.value = size
  offset.value = 0
  fetchTraces()
}

async function openDetail(row) {
  loading.value = true
  try {
    const result = await api.admin.llmTraces.get(row.call_id)
    if (result.ok) {
      currentTrace.value = result.data
      detailVisible.value = true
    } else {
      ElMessage.error(result.data?.detail || '获取详情失败')
    }
  } finally {
    loading.value = false
  }
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatDuration(ms) {
  if (ms == null) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

function formatTokens(tokens) {
  if (tokens == null) return '-'
  return tokens.toLocaleString()
}

function copyToClipboard(text) {
  if (!text) return
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

// Lifecycle
onMounted(fetchTraces)
</script>

<template>
  <div class="llm-trace-manager">
    <!-- Toolbar -->
    <div class="toolbar">
      <el-input
        v-model="filters.source"
        placeholder="来源过滤"
        clearable
        style="width: 160px"
        @keyup.enter="handleSearch"
      />
      <el-input
        v-model="filters.model"
        placeholder="模型过滤"
        clearable
        style="width: 160px"
        @keyup.enter="handleSearch"
      />
      <el-select
        v-model="filters.status"
        placeholder="状态"
        clearable
        style="width: 120px"
      >
        <el-option
          v-for="opt in statusOptions"
          :key="opt.value"
          :label="opt.label"
          :value="opt.value"
        />
      </el-select>
      <el-input
        v-model="filters.trace_id"
        placeholder="Trace ID"
        clearable
        style="width: 200px"
        @keyup.enter="handleSearch"
      />
      <el-button type="primary" @click="handleSearch">
        <el-icon><Search /></el-icon>
        查询
      </el-button>
      <el-button @click="handleReset">
        <el-icon><Refresh /></el-icon>
        重置
      </el-button>
    </div>

    <!-- Table -->
    <el-table :data="traces" v-loading="loading" border>
      <el-table-column prop="call_id" label="Call ID" min-width="160">
        <template #default="{ row }">
          <el-tooltip :content="row.call_id" placement="top">
            <span class="ellipsis">{{ row.call_id }}</span>
          </el-tooltip>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="时间" width="160">
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column prop="source" label="来源" width="120" />
      <el-table-column prop="model" label="模型" width="140" />
      <el-table-column prop="duration_ms" label="耗时" width="90" align="right">
        <template #default="{ row }">
          <el-tag size="small" type="info">{{ formatDuration(row.duration_ms) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="total_tokens" label="Token" width="90" align="right">
        <template #default="{ row }">
          {{ formatTokens(row.total_tokens) }}
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="80" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="row.status === 'success' ? 'success' : 'danger'">
            <el-icon v-if="row.status === 'success'"><Check /></el-icon>
            <el-icon v-else><Close /></el-icon>
            {{ row.status === 'success' ? '成功' : '错误' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="trace_id" label="Trace ID" min-width="140">
        <template #default="{ row }">
          <span v-if="row.trace_id" class="ellipsis">{{ row.trace_id }}</span>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="openDetail(row)">
            <el-icon><View /></el-icon>
            详情
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Pagination -->
    <div class="pagination-bar">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="limit"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>

    <!-- Detail Drawer -->
    <el-drawer
      v-model="detailVisible"
      title="调用详情"
      direction="rtl"
      size="60%"
    >
      <template v-if="currentTrace">
        <div class="detail-content">
          <!-- Basic Info -->
          <el-descriptions :column="2" border>
            <el-descriptions-item label="Call ID">
              <div class="copy-row">
                <span class="ellipsis">{{ currentTrace.call_id }}</span>
                <el-button size="small" text @click="copyToClipboard(currentTrace.call_id)">
                  <el-icon><DocumentCopy /></el-icon>
                </el-button>
              </div>
            </el-descriptions-item>
            <el-descriptions-item label="Trace ID">
              <span class="ellipsis">{{ currentTrace.trace_id || '-' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="来源">{{ currentTrace.source }}</el-descriptions-item>
            <el-descriptions-item label="Provider">{{ currentTrace.provider }}</el-descriptions-item>
            <el-descriptions-item label="模型">{{ currentTrace.model }}</el-descriptions-item>
            <el-descriptions-item label="Base URL">
              <span class="ellipsis">{{ currentTrace.base_url || '-' }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag size="small" :type="currentTrace.status === 'success' ? 'success' : 'danger'">
                {{ currentTrace.status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="耗时">
              <el-icon><Timer /></el-icon>
              {{ formatDuration(currentTrace.duration_ms) }}
            </el-descriptions-item>
            <el-descriptions-item label="Prompt Tokens">
              <el-icon><Cpu /></el-icon>
              {{ formatTokens(currentTrace.prompt_tokens) }}
            </el-descriptions-item>
            <el-descriptions-item label="Completion Tokens">
              {{ formatTokens(currentTrace.completion_tokens) }}
            </el-descriptions-item>
            <el-descriptions-item label="Total Tokens">
              {{ formatTokens(currentTrace.total_tokens) }}
            </el-descriptions-item>
            <el-descriptions-item label="Endpoint">
              {{ currentTrace.endpoint_method || '-' }} {{ currentTrace.endpoint_path || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="Actor">
              {{ currentTrace.actor_type || '-' }} / {{ currentTrace.actor_id || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="Session">
              {{ currentTrace.session_type || '-' }} / {{ currentTrace.session_id || '-' }}
            </el-descriptions-item>
          </el-descriptions>

          <!-- Error Info -->
          <div v-if="currentTrace.error_type" class="section error-section">
            <h4>错误信息</h4>
            <el-alert :title="currentTrace.error_type" type="error" :closable="false">
              <pre>{{ currentTrace.error_message_masked || '无详细错误信息' }}</pre>
            </el-alert>
          </div>

          <!-- Request Readable -->
          <div class="section">
            <div class="section-header">
              <h4>请求内容</h4>
              <el-button size="small" text @click="copyToClipboard(currentTrace.request_readable)">
                <el-icon><DocumentCopy /></el-icon>
                复制
              </el-button>
            </div>
            <el-input
              v-model="currentTrace.request_readable"
              type="textarea"
              :rows="12"
              readonly
            />
          </div>

          <!-- Response Readable -->
          <div class="section">
            <div class="section-header">
              <h4>响应内容</h4>
              <el-button size="small" text @click="copyToClipboard(currentTrace.response_readable)">
                <el-icon><DocumentCopy /></el-icon>
                复制
              </el-button>
            </div>
            <el-input
              v-model="currentTrace.response_readable"
              type="textarea"
              :rows="12"
              readonly
            />
          </div>

          <!-- Raw Payloads -->
          <div class="section">
            <h4>原始请求 (Masked)</h4>
            <el-input
              :model-value="JSON.stringify(currentTrace.request_payload_masked, null, 2)"
              type="textarea"
              :rows="8"
              readonly
            />
          </div>
          <div class="section">
            <h4>原始响应 (Masked)</h4>
            <el-input
              :model-value="JSON.stringify(currentTrace.response_payload_masked, null, 2)"
              type="textarea"
              :rows="8"
              readonly
            />
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.llm-trace-manager {
  padding: 20px;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
  align-items: center;
}

.pagination-bar {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.ellipsis {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.text-muted {
  color: #909399;
}

.detail-content {
  padding: 0 10px;
}

.section {
  margin-top: 20px;
}

.section h4 {
  margin-bottom: 10px;
  font-size: 14px;
  color: #303133;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.copy-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.error-section pre {
  margin: 8px 0 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
}
</style>
