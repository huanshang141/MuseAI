<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../../api/index.js'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh,
  Edit,
  Clock,
  RefreshRight
} from '@element-plus/icons-vue'

// State
const loading = ref(false)
const prompts = ref([])
const selectedCategory = ref('')
const drawerVisible = ref(false)
const versionDialogVisible = ref(false)
const currentPrompt = ref(null)
const versions = ref([])
const versionsLoading = ref(false)
const editForm = ref({
  content: '',
  change_reason: ''
})

// Category labels
const categoryLabels = {
  rag: 'RAG',
  curator: '策展人',
  narrative: '叙事生成',
  query_transform: '查询转换',
  reflection: '反思提示',
  narrative_style: '叙事风格'
}

// Computed
const categories = computed(() => {
  const cats = new Set(prompts.value.map(p => p.category))
  return Array.from(cats).map(c => ({
    value: c,
    label: categoryLabels[c] || c
  }))
})

const filteredPrompts = computed(() => {
  if (!selectedCategory.value) return prompts.value
  return prompts.value.filter(p => p.category === selectedCategory.value)
})

// Methods
async function fetchPrompts() {
  loading.value = true
  try {
    const result = await api.admin.prompts.list()
    if (result.ok) {
      prompts.value = result.data.prompts || []
    } else {
      ElMessage.error(result.data?.detail || '获取提示词列表失败')
    }
  } finally {
    loading.value = false
  }
}

function openEditDrawer(prompt) {
  currentPrompt.value = prompt
  editForm.value = {
    content: prompt.content,
    change_reason: ''
  }
  drawerVisible.value = true
}

async function handleUpdate() {
  if (!editForm.value.content.trim()) {
    ElMessage.warning('内容不能为空')
    return
  }

  loading.value = true
  try {
    const result = await api.admin.prompts.update(currentPrompt.value.key, {
      content: editForm.value.content,
      change_reason: editForm.value.change_reason || null
    })
    if (result.ok) {
      ElMessage.success('更新成功')
      drawerVisible.value = false
      await fetchPrompts()
    } else {
      ElMessage.error(result.data?.detail || '更新失败')
    }
  } finally {
    loading.value = false
  }
}

async function openVersionDialog(prompt) {
  currentPrompt.value = prompt
  versionDialogVisible.value = true
  versionsLoading.value = true
  versions.value = []

  try {
    const result = await api.admin.prompts.listVersions(prompt.key, { limit: 50 })
    if (result.ok) {
      versions.value = result.data.versions || []
    } else {
      ElMessage.error(result.data?.detail || '获取版本历史失败')
    }
  } finally {
    versionsLoading.value = false
  }
}

async function handleRollback(version) {
  try {
    await ElMessageBox.confirm(
      `确定要回滚到版本 ${version.version} 吗？这将创建一个新版本。`,
      '确认回滚',
      { type: 'warning' }
    )
  } catch {
    return
  }

  versionsLoading.value = true
  try {
    const result = await api.admin.prompts.rollback(currentPrompt.value.key, version.version)
    if (result.ok) {
      ElMessage.success('回滚成功')
      // Refresh both versions and prompts list
      await openVersionDialog(currentPrompt.value)
      await fetchPrompts()
    } else {
      ElMessage.error(result.data?.detail || '回滚失败')
    }
  } finally {
    versionsLoading.value = false
  }
}

async function handleReload(key) {
  loading.value = true
  try {
    const result = key
      ? await api.admin.prompts.reload(key)
      : await api.admin.prompts.reloadAll()
    if (result.ok) {
      ElMessage.success(result.data.message || '重载成功')
    } else {
      ElMessage.error(result.data?.detail || '重载失败')
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
    minute: '2-digit'
  })
}

// Lifecycle
onMounted(fetchPrompts)
</script>

<template>
  <div class="prompt-manager">
    <!-- Toolbar -->
    <div class="toolbar">
      <el-select
        v-model="selectedCategory"
        placeholder="按分类筛选"
        clearable
        style="width: 150px"
      >
        <el-option
          v-for="cat in categories"
          :key="cat.value"
          :label="cat.label"
          :value="cat.value"
        />
      </el-select>
      <el-button type="primary" @click="handleReload()">
        <el-icon><Refresh /></el-icon>
        重载全部缓存
      </el-button>
    </div>

    <!-- Prompt List -->
    <el-table :data="filteredPrompts" v-loading="loading" border>
      <el-table-column prop="name" label="名称" min-width="150" />
      <el-table-column prop="key" label="Key" min-width="180">
        <template #default="{ row }">
          <el-tag size="small" type="info">{{ row.key }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="category" label="分类" width="120">
        <template #default="{ row }">
          <el-tag size="small">{{ categoryLabels[row.category] || row.category }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="current_version" label="版本" width="80" align="center">
        <template #default="{ row }">
          <el-tag size="small" type="success">v{{ row.current_version }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="updated_at" label="更新时间" width="160">
        <template #default="{ row }">
          {{ formatDate(row.updated_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="openEditDrawer(row)">
            <el-icon><Edit /></el-icon>
            编辑
          </el-button>
          <el-button size="small" @click="openVersionDialog(row)">
            <el-icon><Clock /></el-icon>
            历史
          </el-button>
          <el-button size="small" @click="handleReload(row.key)">
            <el-icon><RefreshRight /></el-icon>
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Edit Drawer -->
    <el-drawer
      v-model="drawerVisible"
      title="编辑提示词"
      direction="rtl"
      size="50%"
    >
      <template v-if="currentPrompt">
        <div class="drawer-content">
          <!-- Basic Info -->
          <el-descriptions :column="1" border>
            <el-descriptions-item label="Key">
              <el-tag>{{ currentPrompt.key }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="名称">{{ currentPrompt.name }}</el-descriptions-item>
            <el-descriptions-item label="分类">
              {{ categoryLabels[currentPrompt.category] || currentPrompt.category }}
            </el-descriptions-item>
            <el-descriptions-item label="当前版本">
              v{{ currentPrompt.current_version }}
            </el-descriptions-item>
            <el-descriptions-item v-if="currentPrompt.description" label="描述">
              {{ currentPrompt.description }}
            </el-descriptions-item>
          </el-descriptions>

          <!-- Variables -->
          <div v-if="currentPrompt.variables?.length" class="variables-section">
            <h4>可用变量</h4>
            <el-card shadow="never">
              <div v-for="variable in currentPrompt.variables" :key="variable.name" class="variable-item">
                <el-tag size="small" type="info">{{ variable.name }}</el-tag>
                <span class="variable-desc">{{ variable.description }}</span>
              </div>
            </el-card>
          </div>

          <!-- Content Editor -->
          <div class="editor-section">
            <h4>内容 <span class="required">*</span></h4>
            <el-input
              v-model="editForm.content"
              type="textarea"
              :rows="15"
              placeholder="请输入提示词内容"
            />
          </div>

          <!-- Change Reason -->
          <div class="reason-section">
            <h4>变更原因</h4>
            <el-input
              v-model="editForm.change_reason"
              placeholder="请输入变更原因（可选）"
            />
          </div>
        </div>

        <!-- Footer -->
        <div class="drawer-footer">
          <el-button @click="drawerVisible = false">取消</el-button>
          <el-button type="primary" :loading="loading" @click="handleUpdate">
            保存
          </el-button>
        </div>
      </template>
    </el-drawer>

    <!-- Version History Dialog -->
    <el-dialog
      v-model="versionDialogVisible"
      title="版本历史"
      width="700px"
    >
      <el-table :data="versions" v-loading="versionsLoading" border max-height="400">
        <el-table-column prop="version" label="版本" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.version === currentPrompt?.current_version ? 'success' : 'info'">
              v{{ row.version }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="changed_by" label="修改者" width="120">
          <template #default="{ row }">
            {{ row.changed_by || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="change_reason" label="变更原因" min-width="150">
          <template #default="{ row }">
            {{ row.change_reason || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button
              v-if="row.version !== currentPrompt?.current_version"
              type="warning"
              size="small"
              @click="handleRollback(row)"
            >
              回滚
            </el-button>
            <span v-else class="current-label">当前</span>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<style scoped>
.prompt-manager {
  padding: 20px;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.drawer-content {
  padding: 0 20px;
  padding-bottom: 80px; /* 为固定底部按钮栏预留空间 */
}

.variables-section {
  margin-top: 20px;
}

.variables-section h4,
.editor-section h4,
.reason-section h4 {
  margin-bottom: 10px;
  font-size: 14px;
  color: #303133;
}

.variables-section h4 {
  margin-top: 0;
}

.variable-item {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.variable-item:last-child {
  margin-bottom: 0;
}

.variable-desc {
  color: #606266;
  font-size: 13px;
}

.editor-section {
  margin-top: 20px;
}

.reason-section {
  margin-top: 20px;
}

.required {
  color: #f56c6c;
}

.drawer-footer {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 20px;
  background: #fff;
  border-top: 1px solid #e4e7ed;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.current-label {
  color: #909399;
  font-size: 12px;
}
</style>
