<script setup>
import { onMounted } from 'vue'
import { useDocuments } from '../../composables/useDocuments.js'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Document, View, Delete, Loading } from '@element-plus/icons-vue'

const { documents, loading, fetchDocuments, deleteDocument, getDocumentStatus } = useDocuments()

const statusMap = {
  processing: { type: 'warning', text: '处理中' },
  completed: { type: 'success', text: '已完成' },
  failed: { type: 'danger', text: '失败' },
}

async function handleDelete(doc) {
  try {
    await ElMessageBox.confirm('确定删除此文档？', '确认删除', { type: 'warning' })
    const result = await deleteDocument(doc.id)
    if (result.ok) {
      ElMessage.success('删除成功')
    } else {
      ElMessage.error('删除失败')
    }
  } catch {
    // 用户取消
  }
}

async function handleViewStatus(doc) {
  const result = await getDocumentStatus(doc.id)
  if (result.ok) {
    const data = result.data
    ElMessage.success(`文档状态: ${data.status}, 分块数: ${data.chunk_count}`)
  } else {
    ElMessage.error('获取状态失败')
  }
}

onMounted(fetchDocuments)
</script>

<template>
  <div style="flex: 1; overflow-y: auto;">
    <div v-if="loading" style="padding: 20px; text-align: center;">
      <el-icon class="is-loading" style="font-size: 24px;"><Loading /></el-icon>
    </div>
    <div v-else-if="documents.length === 0" style="padding: 20px; text-align: center; color: #909399;">
      暂无文档
    </div>
    <div v-else>
      <div
        v-for="doc in documents"
        :key="doc.id"
        style="padding: 12px 16px; border-bottom: 1px solid #e4e7ed;"
      >
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="flex: 1; overflow: hidden;">
            <div style="font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
              <el-icon style="margin-right: 4px;"><Document /></el-icon>
              {{ doc.filename }}
            </div>
            <div style="font-size: 12px; color: #909399; margin-top: 4px;">
              {{ new Date(doc.created_at).toLocaleString('zh-CN') }}
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <el-tag :type="statusMap[doc.status]?.type || 'info'" size="small">
              {{ statusMap[doc.status]?.text || doc.status }}
            </el-tag>
            <el-button-group size="small">
              <el-tooltip content="查看状态" placement="top">
                <el-button @click="handleViewStatus(doc)" :icon="View" />
              </el-tooltip>
              <el-tooltip content="删除文档" placement="top">
                <el-button @click="handleDelete(doc)" :icon="Delete" type="danger" />
              </el-tooltip>
            </el-button-group>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
