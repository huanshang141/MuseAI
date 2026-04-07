<script setup>
import { ref, onMounted } from 'vue'
import { useAdmin } from '../../composables/useAdmin.js'
import { api } from '../../api/index.js'
import { ElMessage, ElMessageBox } from 'element-plus'

const { loading, createExhibit, updateExhibit, deleteExhibit } = useAdmin()

const exhibits = ref([])
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
  hall: [{ required: true, message: '请输入展厅', trigger: 'blur' }],
  category: [{ required: true, message: '请输入类别', trigger: 'blur' }]
}

onMounted(fetchExhibits)

async function fetchExhibits() {
  const result = await api.admin.listExhibits()
  if (result.ok) {
    exhibits.value = result.data.exhibits || []
  }
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
        <el-icon><Plus /></el-icon>
        添加展品
      </el-button>
    </div>

    <el-table :data="exhibits" v-loading="loading" border>
      <el-table-column prop="name" label="名称" min-width="150" />
      <el-table-column prop="category" label="类别" width="100" />
      <el-table-column prop="hall" label="展厅" width="120" />
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
              <el-input v-model="form.hall" />
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
}
</style>
