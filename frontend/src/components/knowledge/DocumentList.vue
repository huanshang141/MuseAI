<script setup>
import { onMounted, ref } from 'vue'
import { useDocuments } from '../../composables/useDocuments.js'
import { useAuth } from '../../composables/useAuth.js'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, View, Delete } from '@element-plus/icons-vue'

const { documents, loading, fetchDocuments, deleteDocument, getDocumentStatus } = useDocuments()
const { isAdmin } = useAuth()

const tableRef = ref(null)
const selectedRows = ref([])
const batchDeleting = ref(false)

const statusMap = {
  processing: { type: 'warning', text: '处理中' },
  completed: { type: 'success', text: '已完成' },
  failed: { type: 'danger', text: '失败' },
}

function handleSelectionChange(selection) {
  selectedRows.value = selection
}

async function handleDelete(doc) {
  try {
    await ElMessageBox.confirm('确定删除此文档？', '确认删除', { type: 'warning' })
    const result = await deleteDocument(doc.id)
    if (result.ok) {
      ElMessage.success('删除成功')
      selectedRows.value = selectedRows.value.filter(item => item.id !== doc.id)
    } else {
      ElMessage.error(result.data?.detail || '删除失败')
    }
  } catch {
    // 用户取消
  }
}

async function handleBatchDelete() {
  if (!selectedRows.value.length) return

  try {
    await ElMessageBox.confirm(`确定删除已选中的 ${selectedRows.value.length} 个文档吗？`, '批量删除确认', {
      type: 'warning',
    })

    batchDeleting.value = true
    let successCount = 0
    let failedCount = 0

    for (const doc of selectedRows.value) {
      const result = await deleteDocument(doc.id)
      if (result.ok) {
        successCount += 1
      } else {
        failedCount += 1
      }
    }

    selectedRows.value = []
    tableRef.value?.clearSelection()

    if (failedCount === 0) {
      ElMessage.success(`批量删除成功，共删除 ${successCount} 个文档`)
    } else {
      ElMessage.warning(`已删除 ${successCount} 个文档，${failedCount} 个删除失败`)
    }
  } catch {
    // 用户取消
  } finally {
    batchDeleting.value = false
  }
}

async function handleViewStatus(doc) {
  const result = await getDocumentStatus(doc.id)
  if (result.ok) {
    const data = result.data
    ElMessage.success(`文档状态: ${data.status}, 分块数: ${data.chunk_count}`)
  } else {
    ElMessage.error(result.data?.detail || '获取状态失败')
  }
}

onMounted(fetchDocuments)
</script>

<template>
  <div class="document-list">
    <div v-if="isAdmin" class="toolbar">
      <span class="selection-meta">已选 {{ selectedRows.length }} 项</span>
      <el-button
        type="danger"
        plain
        :loading="batchDeleting"
        :disabled="batchDeleting || loading || !selectedRows.length"
        @click="handleBatchDelete"
      >
        批量删除
      </el-button>
    </div>

    <el-table
      v-if="documents.length"
      ref="tableRef"
      :data="documents"
      row-key="id"
      v-loading="loading"
      border
      @selection-change="handleSelectionChange"
    >
      <el-table-column v-if="isAdmin" type="selection" width="50" reserve-selection />
      <el-table-column prop="filename" label="文件名" min-width="220">
        <template #default="{ row }">
          <div class="filename-cell">
            <el-icon><Document /></el-icon>
            <span class="filename-text">{{ row.filename }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="110" align="center">
        <template #default="{ row }">
          <el-tag :type="statusMap[row.status]?.type || 'info'" size="small">
            {{ statusMap[row.status]?.text || row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="上传时间" min-width="180">
        <template #default="{ row }">
          {{ new Date(row.created_at).toLocaleString('zh-CN') }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" size="small" :icon="View" @click="handleViewStatus(row)">状态</el-button>
          <el-button v-if="isAdmin" type="danger" size="small" :icon="Delete" @click="handleDelete(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-else-if="loading" class="table-state">加载中...</div>
    <div v-else class="table-state">暂无文档</div>
  </div>
</template>

<style scoped>
.document-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.selection-meta {
  color: #606266;
  font-size: 13px;
}

.filename-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.filename-text {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.table-state {
  text-align: center;
  color: #909399;
  padding: 20px 0;
}
</style>
