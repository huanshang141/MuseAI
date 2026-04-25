<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../../api/index.js'
import { useAdmin } from '../../composables/useAdmin.js'
import PlusIcon from '../icons/PlusIcon.vue'

const { loading, createHall, updateHall, deleteHall } = useAdmin()

const halls = ref([])
const tableRef = ref(null)
const selectedRows = ref([])
const batchDeleting = ref(false)
const dialogVisible = ref(false)
const isEditing = ref(false)
const formRef = ref(null)

const form = ref({
  slug: '',
  name: '',
  description: '',
  floor: null,
  estimated_duration_minutes: 30,
  display_order: 0,
  is_active: true,
})

const rules = {
  slug: [{ required: true, message: '请输入展厅标识（slug）', trigger: 'blur' }],
  name: [{ required: true, message: '请输入展厅名称', trigger: 'blur' }],
}

onMounted(fetchHalls)

async function fetchHalls() {
  const result = await api.admin.listHalls({ include_inactive: 'true' })
  if (result.ok) {
    halls.value = result.data.halls || []
    selectedRows.value = []
    await nextTick()
    tableRef.value?.clearSelection()
  }
}

function handleAdd() {
  isEditing.value = false
  form.value = {
    slug: '',
    name: '',
    description: '',
    floor: null,
    estimated_duration_minutes: 30,
    display_order: 0,
    is_active: true,
  }
  dialogVisible.value = true
}

function handleEdit(row) {
  isEditing.value = true
  form.value = {
    slug: row.slug,
    name: row.name,
    description: row.description || '',
    floor: row.floor,
    estimated_duration_minutes: row.estimated_duration_minutes,
    display_order: row.display_order,
    is_active: row.is_active,
  }
  dialogVisible.value = true
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(`确定删除展厅 ${row.name} 吗？`, '提示', {
      type: 'warning',
    })

    const result = await deleteHall(row.slug)
    if (result.ok) {
      ElMessage.success('删除成功')
      fetchHalls()
    } else {
      ElMessage.error(result.data?.detail || '删除失败')
    }
  } catch {
    // canceled
  }
}

function handleSelectionChange(selection) {
  selectedRows.value = selection
}

async function handleBatchDelete() {
  if (!selectedRows.value.length) return

  try {
    await ElMessageBox.confirm(`确定删除已选中的 ${selectedRows.value.length} 个展厅吗？`, '批量删除确认', {
      type: 'warning',
    })

    batchDeleting.value = true
    let successCount = 0
    let failedCount = 0

    for (const row of selectedRows.value) {
      const result = await deleteHall(row.slug)
      if (result.ok) {
        successCount += 1
      } else {
        failedCount += 1
      }
    }

    await fetchHalls()

    if (failedCount === 0) {
      ElMessage.success(`批量删除成功，共删除 ${successCount} 个展厅`)
    } else {
      ElMessage.warning(`已删除 ${successCount} 个展厅，${failedCount} 个删除失败`)
    }
  } catch {
    // canceled
  } finally {
    batchDeleting.value = false
  }
}

async function handleSubmit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  const payload = {
    slug: form.value.slug,
    name: form.value.name,
    description: form.value.description || null,
    floor: form.value.floor,
    estimated_duration_minutes: form.value.estimated_duration_minutes,
    display_order: form.value.display_order,
    is_active: form.value.is_active,
  }

  const result = isEditing.value
    ? await updateHall(form.value.slug, {
      name: payload.name,
      description: payload.description,
      floor: payload.floor,
      estimated_duration_minutes: payload.estimated_duration_minutes,
      display_order: payload.display_order,
      is_active: payload.is_active,
    })
    : await createHall(payload)

  if (result.ok) {
    ElMessage.success(isEditing.value ? '更新成功' : '创建成功')
    dialogVisible.value = false
    fetchHalls()
  } else {
    ElMessage.error(result.data?.detail || '操作失败')
  }
}
</script>

<template>
  <div class="hall-manager">
    <div class="toolbar">
      <el-button type="primary" @click="handleAdd">
        <el-icon><PlusIcon /></el-icon>
        添加展厅
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
      :data="halls"
      v-loading="loading"
      border
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="50" reserve-selection />
      <el-table-column prop="name" label="展厅名称" min-width="160" />
      <el-table-column prop="slug" label="标识" min-width="150" />
      <el-table-column prop="floor" label="楼层" width="90" />
      <el-table-column prop="estimated_duration_minutes" label="建议时长(分)" width="120" />
      <el-table-column prop="display_order" label="排序" width="90" />
      <el-table-column label="启用" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'">
            {{ row.is_active ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" @click="handleEdit(row)">编辑</el-button>
          <el-button type="danger" size="small" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="isEditing ? '编辑展厅' : '添加展厅'"
      width="640px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="120px">
        <el-form-item label="展厅标识" prop="slug">
          <el-input v-model="form.slug" :disabled="isEditing" placeholder="例如 relic-hall" />
        </el-form-item>
        <el-form-item label="展厅名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="楼层">
              <el-input-number v-model="form.floor" :min="1" :max="10" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="建议时长(分)">
              <el-input-number v-model="form.estimated_duration_minutes" :min="1" :max="480" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="排序">
              <el-input-number v-model="form.display_order" :min="0" :max="100000" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="启用">
              <el-switch v-model="form.is_active" />
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
.hall-manager {
  padding: 20px;
}

.toolbar {
  margin-bottom: 20px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
</style>
