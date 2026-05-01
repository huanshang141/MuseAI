<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../../api/index.js'
import { ElMessage } from 'element-plus'
import {
  Edit,
  Clock,
  RefreshRight,
  VideoPlay,
  Headset
} from '@element-plus/icons-vue'

const personaLabels = {
  a: { name: '考古学家', color: 'warning' },
  b: { name: '老村民', color: 'success' },
  c: { name: '历史老师', color: 'primary' },
}

const loading = ref(false)
const personas = ref([])
const drawerVisible = ref(false)
const versionDialogVisible = ref(false)
const previewDialogVisible = ref(false)
const currentPersona = ref(null)
const versions = ref([])
const versionsLoading = ref(false)
const presetVoices = [
  { value: '冰糖', label: '冰糖 (中文女声)' },
  { value: '茉莉', label: '茉莉 (中文女声)' },
  { value: '苏打', label: '苏打 (中文男声)' },
  { value: '白桦', label: '白桦 (中文男声)' },
  { value: 'Mia', label: 'Mia (英文女声)' },
  { value: 'Chloe', label: 'Chloe (英文女声)' },
  { value: 'Milo', label: 'Milo (英文男声)' },
  { value: 'Dean', label: 'Dean (英文男声)' },
]

const editForm = ref({
  content: '',
  voice: '',
  voice_description: '',
  change_reason: ''
})
const previewForm = ref({
  voice_description: '',
  sample_text: '大家好，欢迎来到博物馆，我是今天的讲解员'
})
const previewLoading = ref(false)
const previewAudioUrl = ref('')

async function fetchPersonas() {
  loading.value = true
  try {
    const result = await api.admin.ttsPersonas.list()
    if (result.ok) {
      personas.value = result.data.personas || []
    } else {
      ElMessage.error(result.data?.detail || '获取语音角色列表失败')
    }
  } finally {
    loading.value = false
  }
}

function getPersonaLetter(key) {
  return key.replace('tour_tts_persona_', '')
}

function openEditDrawer(persona) {
  currentPersona.value = persona
  editForm.value = {
    content: persona.content,
    voice: persona.voice || '',
    voice_description: persona.voice_description || '',
    change_reason: ''
  }
  drawerVisible.value = true
}

async function handleUpdate() {
  if (!editForm.value.content.trim()) {
    ElMessage.warning('风格提示词不能为空')
    return
  }

  loading.value = true
  try {
    const letter = getPersonaLetter(currentPersona.value.key)
    const result = await api.admin.ttsPersonas.update(letter, {
      content: editForm.value.content,
      voice: editForm.value.voice || null,
      voice_description: editForm.value.voice_description || null,
      change_reason: editForm.value.change_reason || null
    })
    if (result.ok) {
      ElMessage.success('更新成功')
      drawerVisible.value = false
      await fetchPersonas()
    } else {
      ElMessage.error(result.data?.detail || '更新失败')
    }
  } finally {
    loading.value = false
  }
}

function openPreviewDialog(persona) {
  currentPersona.value = persona
  previewForm.value = {
    voice_description: persona.voice_description || '',
    sample_text: '大家好，欢迎来到博物馆，我是今天的讲解员'
  }
  previewAudioUrl.value = ''
  previewDialogVisible.value = true
}

async function handleVoicePreview() {
  if (!previewForm.value.voice_description.trim()) {
    ElMessage.warning('请输入音色描述')
    return
  }

  previewLoading.value = true
  try {
    const result = await api.admin.ttsPersonas.voicePreview({
      voice_description: previewForm.value.voice_description,
      sample_text: previewForm.value.sample_text
    })
    if (result.ok && result.data?.audio) {
      const audioBytes = atob(result.data.audio)
      const arrayBuffer = new Uint8Array(audioBytes.length)
      for (let i = 0; i < audioBytes.length; i++) {
        arrayBuffer[i] = audioBytes.charCodeAt(i)
      }
      const blob = new Blob([arrayBuffer], { type: 'audio/wav' })
      previewAudioUrl.value = URL.createObjectURL(blob)
    } else {
      ElMessage.error(result.data?.detail || '音色预览生成失败')
    }
  } finally {
    previewLoading.value = false
  }
}

async function openVersionDialog(persona) {
  currentPersona.value = persona
  versionDialogVisible.value = true
  versionsLoading.value = true
  versions.value = []

  try {
    const result = await api.admin.prompts.listVersions(persona.key, { limit: 50 })
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
    const { ElMessageBox } = await import('element-plus')
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
    const result = await api.admin.prompts.rollback(currentPersona.value.key, version.version)
    if (result.ok) {
      ElMessage.success('回滚成功')
      await openVersionDialog(currentPersona.value)
      await fetchPersonas()
    } else {
      ElMessage.error(result.data?.detail || '回滚失败')
    }
  } finally {
    versionsLoading.value = false
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

function truncateText(text, maxLen = 40) {
  if (!text) return '-'
  return text.length > maxLen ? text.slice(0, maxLen) + '...' : text
}

onMounted(fetchPersonas)
</script>

<template>
  <div class="tts-persona-manager">
    <div class="toolbar">
      <h3>语音角色管理</h3>
      <el-button type="primary" @click="fetchPersonas">
        <el-icon><RefreshRight /></el-icon>
        刷新
      </el-button>
    </div>

    <el-table :data="personas" v-loading="loading" border>
      <el-table-column label="角色" width="120">
        <template #default="{ row }">
          <el-tag :type="personaLabels[getPersonaLetter(row.key)]?.color || 'info'" size="small">
            {{ personaLabels[getPersonaLetter(row.key)]?.name || row.key }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" min-width="150" />
      <el-table-column label="风格提示词" min-width="200">
        <template #default="{ row }">
          {{ truncateText(row.content) }}
        </template>
      </el-table-column>
      <el-table-column label="音色描述" min-width="200">
        <template #default="{ row }">
          {{ truncateText(row.voice_description) }}
        </template>
      </el-table-column>
      <el-table-column label="预设音色" width="120" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.voice" size="small" type="info">{{ row.voice }}</el-tag>
          <span v-else class="current-label">默认</span>
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
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="openEditDrawer(row)">
            <el-icon><Edit /></el-icon>
            编辑
          </el-button>
          <el-button size="small" @click="openPreviewDialog(row)">
            <el-icon><VideoPlay /></el-icon>
            试听
          </el-button>
          <el-button size="small" @click="openVersionDialog(row)">
            <el-icon><Clock /></el-icon>
            历史
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Edit Drawer -->
    <el-drawer
      v-model="drawerVisible"
      title="编辑语音角色"
      direction="rtl"
      size="50%"
    >
      <template v-if="currentPersona">
        <div class="drawer-content">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="Key">
              <el-tag>{{ currentPersona.key }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="角色">
              <el-tag :type="personaLabels[getPersonaLetter(currentPersona.key)]?.color || 'info'">
                {{ personaLabels[getPersonaLetter(currentPersona.key)]?.name }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="名称">{{ currentPersona.name }}</el-descriptions-item>
            <el-descriptions-item label="当前版本">
              v{{ currentPersona.current_version }}
            </el-descriptions-item>
          </el-descriptions>

          <div class="editor-section">
            <h4>风格提示词 <span class="required">*</span></h4>
            <p class="field-hint">控制语音的语气、语速、风格等表达方式</p>
            <el-input
              v-model="editForm.content"
              type="textarea"
              :rows="6"
              placeholder="请输入风格提示词"
            />
          </div>

          <div class="editor-section">
            <h4>预设音色</h4>
            <p class="field-hint">选择该角色使用的预设音色，留空则使用全局默认音色</p>
            <el-select
              v-model="editForm.voice"
              placeholder="使用全局默认音色"
              clearable
              style="width: 100%"
            >
              <el-option
                v-for="v in presetVoices"
                :key="v.value"
                :label="v.label"
                :value="v.value"
              />
            </el-select>
          </div>

          <div class="editor-section">
            <h4>音色描述</h4>
            <p class="field-hint">描述角色的嗓音特征，用于音色设计预览（如：五十多岁的中年男性，声音沉稳浑厚）</p>
            <el-input
              v-model="editForm.voice_description"
              type="textarea"
              :rows="3"
              placeholder="请输入音色描述"
            />
          </div>

          <div class="editor-section">
            <h4>变更原因</h4>
            <el-input
              v-model="editForm.change_reason"
              placeholder="请输入变更原因（可选）"
            />
          </div>
        </div>

        <div class="drawer-footer">
          <el-button @click="drawerVisible = false">取消</el-button>
          <el-button type="primary" :loading="loading" @click="handleUpdate">
            保存
          </el-button>
        </div>
      </template>
    </el-drawer>

    <!-- Voice Preview Dialog -->
    <el-dialog
      v-model="previewDialogVisible"
      title="音色设计试听"
      width="600px"
    >
      <template v-if="currentPersona">
        <div class="preview-content">
          <div class="editor-section">
            <h4>音色描述</h4>
            <p class="field-hint">描述想要的声音特征（如年龄、性别、口音、语调等）</p>
            <el-input
              v-model="previewForm.voice_description"
              type="textarea"
              :rows="3"
              placeholder="例如：五十多岁的中年男性，北方口音，语速缓慢沉稳"
            />
          </div>

          <div class="editor-section">
            <h4>试听文本</h4>
            <el-input
              v-model="previewForm.sample_text"
              type="textarea"
              :rows="2"
              placeholder="请输入试听文本"
            />
          </div>

          <el-button
            type="primary"
            :loading="previewLoading"
            @click="handleVoicePreview"
            style="margin-top: 12px"
          >
            <el-icon><Headset /></el-icon>
            生成试听
          </el-button>

          <div v-if="previewAudioUrl" class="audio-player">
            <audio :src="previewAudioUrl" controls autoplay style="width: 100%" />
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- Version History Dialog -->
    <el-dialog
      v-model="versionDialogVisible"
      title="版本历史"
      width="700px"
    >
      <el-table :data="versions" v-loading="versionsLoading" border max-height="400">
        <el-table-column prop="version" label="版本" width="80" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.version === currentPersona?.current_version ? 'success' : 'info'">
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
              v-if="row.version !== currentPersona?.current_version"
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
.tts-persona-manager {
  padding: 20px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.toolbar h3 {
  margin: 0;
  font-size: 16px;
}

.drawer-content {
  padding: 0 20px;
  padding-bottom: 80px;
}

.editor-section {
  margin-top: 20px;
}

.editor-section h4 {
  margin-bottom: 4px;
  font-size: 14px;
  color: var(--el-text-color-primary);
}

.field-hint {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.required {
  color: var(--el-color-danger);
}

.drawer-footer {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 20px;
  background: var(--el-bg-color);
  border-top: 1px solid var(--el-border-color-light);
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.audio-player {
  margin-top: 16px;
  padding: 12px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
}

.current-label {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
