<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../../api/index.js'
import { useAdmin } from '../../composables/useAdmin.js'
import { CATEGORY_OPTIONS } from '../../constants/categories.js'
import {
  BANPO_HALLS,
  getCategoryLabel,
  getHallDisplayName,
  mergeHallsWithContract,
  normalizeHallSlug,
} from '../../constants/banpo.js'

const { loading, createExhibit, updateExhibit, deleteExhibit } = useAdmin()

const tableRef = ref(null)
const formRef = ref(null)
const exhibits = ref([])
const halls = ref([])
const selectedRows = ref([])
const batchHall = ref('')
const batchDeleting = ref(false)
const batchBinding = ref(false)
const problemResolving = ref(false)
const dialogVisible = ref(false)
const isEditing = ref(false)

const filters = reactive({
  keyword: '',
  hall: '',
  category: '',
  status: 'active',
})

const form = reactive({
  id: null,
  name: '',
  description: '',
  location_x: 0,
  location_y: 0,
  floor: 1,
  hall: 'basic-exhibition-hall',
  category: 'painted_pottery',
  era: '新石器时代·仰韶文化',
  importance: 3,
  estimated_visit_time: 8,
  document_id: null,
  is_active: true,
})

const rules = {
  name: [{ required: true, message: '请输入展品名称', trigger: 'blur' }],
  hall: [{ required: true, message: '请选择所属展厅', trigger: 'change' }],
  category: [{ required: true, message: '请选择展品分类', trigger: 'change' }],
  description: [{ required: true, message: '请输入展品简介', trigger: 'blur' }],
}

const categoryOptions = computed(() => CATEGORY_OPTIONS.filter((item) => item.value))
const canonicalHalls = computed(() => halls.value.filter((hall) => hall.is_active !== false))
const activeHallSlugs = computed(() => new Set(canonicalHalls.value.map((hall) => hall.slug)))

const normalizedExhibits = computed(() => exhibits.value.map(normalizeExhibit))
const activeNormalizedExhibits = computed(() => normalizedExhibits.value.filter((item) => item.is_active !== false))

const filteredExhibits = computed(() => {
  const q = filters.keyword.trim().toLowerCase()
  return normalizedExhibits.value.filter((item) => {
    const matchesKeyword = !q
      || String(item.name || '').toLowerCase().includes(q)
      || String(item.description || '').toLowerCase().includes(q)
      || String(item.era || '').toLowerCase().includes(q)
    const matchesHall = !filters.hall || item.hall === filters.hall
    const matchesCategory = !filters.category || item.category === filters.category
    const matchesStatus = filters.status === 'all'
      || (filters.status === 'active' && item.is_active !== false)
      || (filters.status === 'inactive' && item.is_active === false)
    return matchesKeyword && matchesHall && matchesCategory && matchesStatus
  })
})

const nonExhibitRows = computed(() => activeNormalizedExhibits.value.filter((item) => isNonExhibitName(item.name)))
const unmappedRows = computed(() => activeNormalizedExhibits.value.filter((item) => !activeHallSlugs.value.has(item.hall)))
const problemRows = computed(() => [...nonExhibitRows.value, ...unmappedRows.value])

const stats = computed(() => [
  { label: '展项总数', value: normalizedExhibits.value.length, hint: '后台展品库' },
  { label: '可展示', value: normalizedExhibits.value.filter((item) => item.is_active !== false).length, hint: '小程序可检索' },
  { label: '展厅覆盖', value: `${coveredHallCount.value}/${BANPO_HALLS.length}`, hint: 'canonical slug' },
  { label: '需处理', value: problemRows.value.length, hint: '非展品或未绑定展厅' },
])

const coveredHallCount = computed(() => {
  const used = new Set(normalizedExhibits.value.map((item) => item.hall).filter(Boolean))
  return BANPO_HALLS.filter((hall) => used.has(hall.slug)).length
})

onMounted(async () => {
  await Promise.all([fetchHalls(), fetchExhibits()])
})

function normalizeExhibit(item) {
  const rawHall = item.hall || item.hall_slug || item.hallSlug
  const hall = normalizeHallSlug(rawHall)
  return {
    ...item,
    rawHall,
    hall,
    hallName: getHallDisplayName(hall),
    categoryLabel: getCategoryLabel(item.category),
    activeText: item.is_active === false ? '停用' : '启用',
    nonExhibit: isNonExhibitName(item.name),
  }
}

async function fetchHalls() {
  const result = await api.admin.listHalls({ include_inactive: 'true' })
  halls.value = result.ok ? mergeHallsWithContract(result.data.halls || []) : mergeHallsWithContract([])
}

async function fetchExhibits() {
  const result = await api.admin.listExhibits({ limit: 1000 })
  if (result.ok) {
    exhibits.value = result.data.exhibits || []
    selectedRows.value = []
    await nextTick()
    tableRef.value?.clearSelection?.()
  } else {
    ElMessage.error(result.data?.detail || '获取展品失败')
  }
}

function isNonExhibitName(name = '') {
  const exactNames = new Set(['半坡人', '生态环境', '临展厅一当期主题', '临展厅二当期主题'])
  return exactNames.has(String(name).trim())
}

function resetForm() {
  Object.assign(form, {
    id: null,
    name: '',
    description: '',
    location_x: 0,
    location_y: 0,
    floor: 1,
    hall: canonicalHalls.value[0]?.slug || 'basic-exhibition-hall',
    category: 'painted_pottery',
    era: '新石器时代·仰韶文化',
    importance: 3,
    estimated_visit_time: 8,
    document_id: null,
    is_active: true,
  })
}

function handleAdd() {
  isEditing.value = false
  resetForm()
  dialogVisible.value = true
}

function handleEdit(row) {
  isEditing.value = true
  Object.assign(form, {
    id: row.id,
    name: row.name || '',
    description: row.description || '',
    location_x: row.location_x ?? 0,
    location_y: row.location_y ?? 0,
    floor: row.floor || 1,
    hall: normalizeHallSlug(row.hall || row.hall_slug || row.hallSlug) || 'basic-exhibition-hall',
    category: row.category || 'painted_pottery',
    era: row.era || '新石器时代·仰韶文化',
    importance: row.importance || 3,
    estimated_visit_time: row.estimated_visit_time || 8,
    document_id: row.document_id || null,
    is_active: row.is_active !== false,
  })
  dialogVisible.value = true
}

function buildPayload() {
  return {
    name: form.name.trim(),
    description: form.description.trim(),
    location_x: Number(form.location_x) || 0,
    location_y: Number(form.location_y) || 0,
    floor: Number(form.floor) || 1,
    hall: normalizeHallSlug(form.hall),
    category: form.category,
    era: form.era.trim(),
    importance: Number(form.importance) || 3,
    estimated_visit_time: Number(form.estimated_visit_time) || 8,
    document_id: form.document_id || null,
    is_active: Boolean(form.is_active),
  }
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  const payload = buildPayload()
  const result = isEditing.value
    ? await updateExhibit(form.id, payload)
    : await createExhibit(payload)

  if (result.ok) {
    ElMessage.success(isEditing.value ? '展品已更新' : '展品已创建')
    dialogVisible.value = false
    await fetchExhibits()
  } else {
    ElMessage.error(result.data?.detail || '保存失败')
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除「${row.name}」吗？`, '删除确认', { type: 'warning' })
    const result = await deleteExhibit(row.id)
    if (result.ok) {
      ElMessage.success('展品已删除')
      await fetchExhibits()
    } else {
      ElMessage.error(result.data?.detail || '删除失败')
    }
  } catch {
    // user cancelled
  }
}

function handleSelectionChange(selection) {
  selectedRows.value = selection
}

async function handleResolveProblemRows() {
  const rowsToDisable = nonExhibitRows.value
  if (!rowsToDisable.length) {
    ElMessage.warning('未绑定展厅的展项需要选择行后批量绑定展厅，或逐条编辑所属展厅')
    return
  }

  try {
    await ElMessageBox.confirm(
      `将停用 ${rowsToDisable.length} 条可能不是展品的条目。未绑定展厅的展项不会自动停用，请选择行后批量绑定展厅。是否继续？`,
      '处理需处理项',
      { type: 'warning' },
    )
    problemResolving.value = true
    let successCount = 0
    let failedCount = 0

    for (const row of rowsToDisable) {
      const result = await updateExhibit(row.id, { is_active: false })
      if (result.ok) successCount += 1
      else failedCount += 1
    }
    await fetchExhibits()
    if (failedCount) {
      ElMessage.warning(`已处理 ${successCount} 条，${failedCount} 条失败`)
    } else {
      ElMessage.success(`已处理 ${successCount} 条异常项`)
    }
  } catch {
    // user cancelled
  } finally {
    problemResolving.value = false
  }
}

async function handleBatchBindHall() {
  if (!selectedRows.value.length || !batchHall.value) return
  try {
    await ElMessageBox.confirm(
      `确定将已选中的 ${selectedRows.value.length} 件展项绑定到「${getHallDisplayName(batchHall.value)}」吗？`,
      '批量绑定展厅',
      { type: 'warning' },
    )
    batchBinding.value = true
    let successCount = 0
    let failedCount = 0
    for (const row of selectedRows.value) {
      const result = await updateExhibit(row.id, { hall: batchHall.value })
      if (result.ok) successCount += 1
      else failedCount += 1
    }
    await fetchExhibits()
    if (failedCount) {
      ElMessage.warning(`已绑定 ${successCount} 件，${failedCount} 件失败`)
    } else {
      ElMessage.success(`已绑定 ${successCount} 件展项`)
    }
  } catch {
    // user cancelled
  } finally {
    batchBinding.value = false
  }
}

async function handleBatchDelete() {
  if (!selectedRows.value.length) return
  try {
    await ElMessageBox.confirm(`确定删除已选中的 ${selectedRows.value.length} 件展品吗？`, '批量删除确认', {
      type: 'warning',
    })
    batchDeleting.value = true
    let successCount = 0
    let failedCount = 0
    for (const row of selectedRows.value) {
      const result = await deleteExhibit(row.id)
      if (result.ok) successCount += 1
      else failedCount += 1
    }
    await fetchExhibits()
    if (failedCount) {
      ElMessage.warning(`已删除 ${successCount} 件，${failedCount} 件失败`)
    } else {
      ElMessage.success(`已删除 ${successCount} 件展品`)
    }
  } catch {
    // user cancelled
  } finally {
    batchDeleting.value = false
  }
}
</script>

<template>
  <div class="exhibit-manager">
    <header class="admin-hero">
      <div>
        <span class="kicker">展品契约</span>
        <h2>半坡展项管理</h2>
        <p>
          这里维护小程序“搜展品”、展品详情、OCR 识别 fallback 和报告展项统计使用的数据。
          展项需绑定半坡 canonical hall slug；明显不是展品的条目会被标记，避免进入小程序搜索结果。
        </p>
      </div>
      <div class="hero-actions">
        <el-button @click="fetchExhibits">刷新</el-button>
        <el-button
          type="warning"
          :loading="problemResolving"
          :disabled="problemResolving || !problemRows.length"
          @click="handleResolveProblemRows"
        >
          处理需处理项
        </el-button>
        <el-button type="primary" @click="handleAdd">添加展品</el-button>
      </div>
    </header>

    <section class="stat-grid">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <span class="stat-hint">{{ item.hint }}</span>
      </article>
    </section>

    <el-alert
      v-if="nonExhibitRows.length"
      type="warning"
      :closable="false"
      show-icon
      class="data-alert"
      title="检测到可能不是展品的条目"
    >
      <template #default>
        {{ nonExhibitRows.map((item) => item.name).join('、') }}
        不应出现在小程序“搜展品”结果中，建议改为资料条目或从展品库删除。
      </template>
    </el-alert>

    <el-alert
      v-if="unmappedRows.length"
      type="error"
      :closable="false"
      show-icon
      class="data-alert"
      title="检测到展厅映射异常"
    >
      <template #default>
        有 {{ unmappedRows.length }} 条展项未绑定到当前半坡 canonical slug，会影响展厅筛选、报告统计和 OCR 匹配。
        可勾选这些展项后，在工具栏选择展厅并批量绑定。
      </template>
    </el-alert>

    <section class="toolbar">
      <el-input v-model="filters.keyword" placeholder="搜索展品名称、简介或年代" clearable />
      <el-select v-model="filters.hall" placeholder="全部展厅" clearable filterable>
        <el-option v-for="hall in canonicalHalls" :key="hall.slug" :label="hall.name" :value="hall.slug" />
      </el-select>
      <el-select v-model="filters.category" placeholder="全部分类" clearable>
        <el-option v-for="category in categoryOptions" :key="category.value" :label="category.label" :value="category.value" />
      </el-select>
      <el-select v-model="filters.status" placeholder="状态">
        <el-option label="启用展项" value="active" />
        <el-option label="停用展项" value="inactive" />
        <el-option label="全部状态" value="all" />
      </el-select>
      <el-select v-model="batchHall" placeholder="批量绑定展厅" clearable filterable>
        <el-option v-for="hall in canonicalHalls" :key="hall.slug" :label="hall.name" :value="hall.slug" />
      </el-select>
      <el-button
        type="primary"
        plain
        :loading="batchBinding"
        :disabled="batchBinding || !selectedRows.length || !batchHall"
        @click="handleBatchBindHall"
      >
        绑定所选
      </el-button>
      <el-button
        type="danger"
        plain
        :loading="batchDeleting"
        :disabled="batchDeleting || !selectedRows.length"
        @click="handleBatchDelete"
      >
        批量删除 ({{ selectedRows.length }})
      </el-button>
    </section>

    <el-table
      ref="tableRef"
      :data="filteredExhibits"
      row-key="id"
      v-loading="loading"
      class="exhibit-table"
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="48" reserve-selection />
      <el-table-column label="展项" min-width="300">
        <template #default="{ row }">
          <div class="exhibit-cell">
            <span class="exhibit-icon">🏺</span>
            <div>
              <div class="exhibit-name">
                {{ row.name }}
                <el-tag v-if="row.nonExhibit" type="warning" size="small">非展品候选</el-tag>
                <el-tag v-if="!activeHallSlugs.has(row.hall)" type="danger" size="small">未绑定展厅</el-tag>
                <el-tag v-if="row.is_active === false" type="info" size="small">停用</el-tag>
              </div>
              <div class="exhibit-desc">{{ row.description || '暂无简介' }}</div>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="所属展厅" min-width="170">
        <template #default="{ row }">
          <div class="hall-cell">
            <strong>{{ row.hallName }}</strong>
            <span>{{ row.hall || row.rawHall || '未绑定 canonical slug' }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="分类" min-width="150">
        <template #default="{ row }">
          <el-tag effect="plain">{{ row.categoryLabel }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="era" label="年代" min-width="170" />
      <el-table-column label="重要度" width="130">
        <template #default="{ row }">
          <el-rate :model-value="row.importance || 3" disabled />
        </template>
      </el-table-column>
      <el-table-column label="参观" width="90">
        <template #default="{ row }">{{ row.estimated_visit_time || 0 }} 分</template>
      </el-table-column>
      <el-table-column label="操作" width="170">
        <template #default="{ row }">
          <el-button size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button type="danger" size="small" plain @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="isEditing ? '编辑展品' : '添加展品'" width="720px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="展品名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="简介" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="4" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="所属展厅" prop="hall">
              <el-select v-model="form.hall" filterable style="width: 100%;">
                <el-option v-for="hall in canonicalHalls" :key="hall.slug" :label="hall.name" :value="hall.slug" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="分类" prop="category">
              <el-select v-model="form.category" style="width: 100%;">
                <el-option v-for="category in categoryOptions" :key="category.value" :label="category.label" :value="category.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="年代">
              <el-input v-model="form.era" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="参观时长">
              <el-input-number v-model="form.estimated_visit_time" :min="1" :max="60" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="楼层">
              <el-input-number v-model="form.floor" :min="1" :max="5" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="重要度">
              <el-input-number v-model="form.importance" :min="1" :max="5" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="启用">
              <el-switch v-model="form.is_active" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="坐标 X">
              <el-input-number v-model="form.location_x" :step="0.1" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="坐标 Y">
              <el-input-number v-model="form.location_y" :step="0.1" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.exhibit-manager {
  min-height: 100%;
  padding: 28px 34px 56px;
  background: linear-gradient(180deg, #fffdf9 0%, #f8f2ea 100%);
}

.admin-hero {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
  margin-bottom: 16px;
  padding: 24px;
  border: 1px solid rgba(126, 91, 65, 0.16);
  border-radius: 16px;
  background: #fffaf3;
  box-shadow: 0 14px 36px rgba(77, 49, 31, 0.07);
}

.kicker {
  color: #c57548;
  font-size: 13px;
  font-weight: 700;
}

.admin-hero h2 {
  margin: 8px 0;
  color: #2f2118;
  font-size: 28px;
}

.admin-hero p {
  max-width: 820px;
  margin: 0;
  color: #7e6a59;
  line-height: 1.7;
}

.hero-actions {
  display: flex;
  gap: 10px;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  display: grid;
  gap: 6px;
  padding: 16px;
  border: 1px solid rgba(126, 91, 65, 0.14);
  border-radius: 12px;
  background: #fffaf3;
}

.stat-label,
.stat-hint {
  color: #8a7565;
  font-size: 13px;
}

.stat-card strong {
  color: #2f2118;
  font-size: 26px;
}

.data-alert {
  margin-bottom: 14px;
}

.toolbar {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) 200px 170px 140px 200px auto auto;
  gap: 10px;
  margin-bottom: 16px;
}

.exhibit-table {
  border-radius: 12px;
  overflow: hidden;
}

.exhibit-cell {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.exhibit-icon {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 10px;
  background: #f1e4d4;
  font-size: 22px;
}

.exhibit-name {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  color: #2f2118;
  font-weight: 700;
}

.exhibit-desc {
  display: -webkit-box;
  margin-top: 4px;
  overflow: hidden;
  color: #7b6758;
  line-height: 1.45;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.hall-cell {
  display: grid;
  gap: 3px;
}

.hall-cell strong {
  color: #2f2118;
}

.hall-cell span {
  color: #9a8575;
  font-size: 12px;
}

@media (max-width: 1180px) {
  .toolbar,
  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .exhibit-manager {
    padding: 18px;
  }

  .admin-hero,
  .hero-actions {
    flex-direction: column;
  }

  .toolbar,
  .stat-grid {
    grid-template-columns: 1fr;
  }
}
</style>
