<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { useAdmin } from '../../composables/useAdmin.js'
import { api } from '../../api/index.js'
import { ElMessage, ElMessageBox } from 'element-plus'
import PlusIcon from '../icons/PlusIcon.vue'

const { loading, createExhibit, updateExhibit, deleteExhibit } = useAdmin()

const exhibits = ref([])
const halls = ref([])
const tableRef = ref(null)
const selectedRows = ref([])
const batchDeleting = ref(false)
const dialogVisible = ref(false)
const isEditing = ref(false)
const formRef = ref(null)

const form = ref({
  name: '',
  description: '',
  location_x: 0,
  location_y: 0,
  floor: 1,
  hall: '',
  category: '',
  era: '',
  importance: 3,
  estimated_visit_time: 10
})

const rules = {
  name: [{ required: true, message: '请输入展品名称', trigger: 'blur' }],
  hall: [{ required: true, message: '请选择展厅', trigger: 'change' }],
  category: [{ required: true, message: '请输入类别', trigger: 'blur' }]
}

onMounted(async () => {
  await Promise.all([fetchExhibits(), fetchHalls()])
})

async function fetchExhibits() {
  const result = await api.admin.listExhibits()
  if (result.ok) {
    exhibits.value = result.data.exhibits || []
    selectedRows.value = []
    await nextTick()
    tableRef.value?.clearSelection()
  }
}

async function fetchHalls() {
  const result = await api.admin.listHalls({ include_inactive: 'false' })
  if (result.ok) {
    halls.value = result.data.halls || []
  }
}

function getHallLabel(slug) {
  const matched = halls.value.find(h => h.slug === slug)
  return matched?.name || slug
}

function hasCurrentHallOption() {
  return halls.value.some(h => h.slug === form.value.hall)
}

function handleAdd() {
  isEditing.value = false
  form.value = {
    name: '',
    description: '',
    location_x: 0,
    location_y: 0,
    floor: 1,
    hall: '',
    category: '',
    era: '',
    importance: 3,
    estimated_visit_time: 10
  }
  dialogVisible.value = true
}

function handleEdit(row) {
  isEditing.value = true
  form.value = { ...row }
  dialogVisible.value = true
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确定要删除这个展品吗？', '提示', {
      type: 'warning'
    })
    const result = await deleteExhibit(row.id)
    if (result.ok) {
      ElMessage.success('删除成功')
      fetchExhibits()
    } else {
      ElMessage.error(result.data?.detail || '删除失败')
    }
  } catch {
    // Cancelled
  }
}

function handleSelectionChange(selection) {
  selectedRows.value = selection
}

async function handleBatchDelete() {
  if (!selectedRows.value.length) return

  try {
    await ElMessageBox.confirm(`确定删除已选中的 ${selectedRows.value.length} 个展品吗？`, '批量删除确认', {
      type: 'warning',
    })

    batchDeleting.value = true
    let successCount = 0
    let failedCount = 0

    for (const row of selectedRows.value) {
      const result = await deleteExhibit(row.id)
      if (result.ok) {
        successCount += 1
      } else {
        failedCount += 1
      }
    }

    await fetchExhibits()

    if (failedCount === 0) {
      ElMessage.success(`批量删除成功，共删除 ${successCount} 个展品`)
    } else {
      ElMessage.warning(`已删除 ${successCount} 个展品，${failedCount} 个删除失败`)
    }
  } catch {
    // Cancelled
  } finally {
    batchDeleting.value = false
  }
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  const result = isEditing.value
    ? await updateExhibit(form.value.id, form.value)
    : await createExhibit(form.value)

  if (result.ok) {
    ElMessage.success(isEditing.value ? '更新成功' : '创建成功')
    dialogVisible.value = false
    fetchExhibits()
  } else {
    ElMessage.error(result.data?.detail || '操作失败')
  }
}
</script>

<template>
  <div class="exhibit-manager">
    <div class="toolbar">
      <el-button type="primary" @click="handleAdd">
        <el-icon><PlusIcon /></el-icon>
        添加展品
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
    </div>

    <el-table
      ref="tableRef"
      :data="exhibits"
      row-key="id"
      v-loading="loading"
      border
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="50" reserve-selection />
      <el-table-column prop="name" label="名称" min-width="150" />
      <el-table-column prop="category" label="类别" width="100" />
      <el-table-column prop="hall" label="展厅" min-width="140">
        <template #default="{ row }">
          {{ getHallLabel(row.hall) }}
        </template>
      </el-table-column>
      <el-table-column prop="floor" label="楼层" width="80" />
      <el-table-column prop="importance" label="重要性" width="90">
        <template #default="{ row }">
          <el-rate :model-value="row.importance" disabled />
        </template>
      </el-table-column>
      <el-table-column prop="estimated_visit_time" label="参观时间(分)" width="110" />
      <el-table-column label="操作" width="150" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button type="danger" size="small" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- Add/Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑展品' : '添加展品'"
      width="600px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="位置X">
              <el-input-number v-model="form.location_x" :min="0" :max="800" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="位置Y">
              <el-input-number v-model="form.location_y" :min="0" :max="600" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="楼层">
              <el-input-number v-model="form.floor" :min="1" :max="3" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="展厅" prop="hall">
              <el-select v-model="form.hall" placeholder="请选择展厅" filterable style="width: 100%;">
                <el-option
                  v-for="hall in halls"
                  :key="hall.slug"
                  :label="hall.name"
                  :value="hall.slug"
                >
                  <div style="display: flex; justify-content: space-between; gap: 8px;">
                    <span>{{ hall.name }}</span>
                    <span style="color: #909399; font-size: 12px;">{{ hall.slug }}</span>
                  </div>
                </el-option>
                <el-option
                  v-if="form.hall && !hasCurrentHallOption()"
                  :label="form.hall"
                  :value="form.hall"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="类别" prop="category">
              <el-input v-model="form.category" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="年代">
              <el-input v-model="form.era" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="重要性">
              <el-slider v-model="form.importance" :min="1" :max="5" show-stops />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="参观时间">
              <el-input-number v-model="form.estimated_visit_time" :min="5" :max="60" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.exhibit-manager {
  padding: 20px;
}

.toolbar {
  margin-bottom: 20px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
</style>
