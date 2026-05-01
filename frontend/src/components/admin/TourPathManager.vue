<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { useAdmin } from '../../composables/useAdmin.js'
import { api } from '../../api/index.js'
import { ElMessage, ElMessageBox } from 'element-plus'
import PlusIcon from '../icons/PlusIcon.vue'
import { EmptyState } from '../../design-system/components/index.js'

const { loading, createTourPath, updateTourPath, deleteTourPath } = useAdmin()

const tourPaths = ref([])
const tableRef = ref(null)
const selectedRows = ref([])
const batchDeleting = ref(false)
const dialogVisible = ref(false)
const isEditing = ref(false)
const formRef = ref(null)

const form = ref({
  name: '',
  description: '',
  exhibit_ids: [],
  estimated_duration: 60
})

const rules = {
  name: [{ required: true, message: '请输入路线名称', trigger: 'blur' }]
}

onMounted(fetchTourPaths)

async function fetchTourPaths() {
  const result = await api.admin.listTourPaths()
  if (result.ok) {
    tourPaths.value = result.data.tour_paths || result.data || []
    selectedRows.value = []
    await nextTick()
    tableRef.value?.clearSelection()
  }
}

function handleAdd() {
  isEditing.value = false
  form.value = {
    name: '',
    description: '',
    exhibit_ids: [],
    estimated_duration: 60
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
    await ElMessageBox.confirm('确定要删除这个路线吗？', '提示', {
      type: 'warning'
    })
    const result = await deleteTourPath(row.id)
    if (result.ok) {
      ElMessage.success('删除成功')
      fetchTourPaths()
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
    await ElMessageBox.confirm(`确定删除已选中的 ${selectedRows.value.length} 条路线吗？`, '批量删除确认', {
      type: 'warning',
    })

    batchDeleting.value = true
    let successCount = 0
    let failedCount = 0

    for (const row of selectedRows.value) {
      const result = await deleteTourPath(row.id)
      if (result.ok) {
        successCount += 1
      } else {
        failedCount += 1
      }
    }

    await fetchTourPaths()

    if (failedCount === 0) {
      ElMessage.success(`批量删除成功，共删除 ${successCount} 条路线`)
    } else {
      ElMessage.warning(`已删除 ${successCount} 条路线，${failedCount} 条删除失败`)
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
    ? await updateTourPath(form.value.id, form.value)
    : await createTourPath(form.value)

  if (result.ok) {
    ElMessage.success(isEditing.value ? '更新成功' : '创建成功')
    dialogVisible.value = false
    fetchTourPaths()
  } else {
    ElMessage.error(result.data?.detail || '操作失败')
  }
}
</script>

<template>
  <div class="tour-path-manager">
    <div class="toolbar">
      <el-button type="primary" @click="handleAdd">
        <el-icon><PlusIcon /></el-icon>
        添加路线
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

    <EmptyState v-if="!tourPaths.length" title="暂无路线数据" description="先创建一条导览路线。">
      <el-button type="primary" @click="handleAdd">添加第一条路线</el-button>
    </EmptyState>

    <el-table
      v-else
      ref="tableRef"
      :data="tourPaths"
      row-key="id"
      v-loading="loading"
      border
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="50" reserve-selection />
      <el-table-column prop="name" label="路线名称" min-width="150" />
      <el-table-column prop="description" label="描述" min-width="200" />
      <el-table-column prop="estimated_duration" label="预计时长(分钟)" width="120" />
      <el-table-column prop="exhibit_count" label="展品数量" width="100" />
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
      :title="isEditing ? '编辑路线' : '添加路线'"
      width="500px"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="路线名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="预计时长">
          <el-input-number v-model="form.estimated_duration" :min="30" :max="180" :step="15" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.tour-path-manager {
  padding: 20px;
}

.toolbar {
  margin-bottom: 20px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
</style>
